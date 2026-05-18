from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from macos_system_data_scanner.classifier import classify_entry
from macos_system_data_scanner.models import (
    CategorySummary,
    ClassifiedFinding,
    ObservedEntry,
    ScanOptions,
    ScanReport,
    ScanSnapshot,
)


def build_report(snapshot: ScanSnapshot, options: ScanOptions) -> ScanReport:
    category_summaries = [
        CategorySummary(
            category=category,
            category_label=label,
            review_guidance=guidance,
            total_size_bytes=values["total_size_bytes"],
            item_count=values["item_count"],
        )
        for (category, label, guidance), values in snapshot.category_totals.items()
    ]
    category_summaries.sort(key=lambda summary: summary.total_size_bytes, reverse=True)

    directory_candidates = _build_directory_candidates(snapshot)
    visible_directories = [
        finding
        for finding in directory_candidates
        if finding.size_bytes >= options.minimum_report_size_bytes
    ]
    visible_directories = _suppress_target_roots(visible_directories, snapshot.included_targets)
    visible_directories = _collapse_overlapping_directories(visible_directories)
    top_directories = visible_directories[: options.top_directories]
    top_files = [classify_entry(entry) for entry in snapshot.entries]
    unknown_file_items = [classify_entry(entry) for entry in snapshot.unknown_entries]

    unknown_large_items = list(unknown_file_items)
    for entry in top_directories:
        if entry.category == "unknown":
            _record_top_finding(
                unknown_large_items,
                entry,
                max(options.top_directories, options.top_files),
            )

    return ScanReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        included_targets=snapshot.included_targets,
        options=options,
        total_observed_bytes=snapshot.total_observed_bytes,
        category_summaries=category_summaries,
        top_directories=top_directories,
        top_files=top_files,
        unknown_large_items=unknown_large_items[: max(options.top_directories, options.top_files)],
        limitations=snapshot.limitations,
    )


def write_json_report(report: ScanReport, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(report.to_dict(), handle, indent=2, sort_keys=False)
        handle.write("\n")


def write_markdown_report(report: ScanReport, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown_report(report), encoding="utf-8")


def render_markdown_report(report: ScanReport) -> str:
    lines = [
        "# macOS System Data Scan Report",
        "",
        f"- Generated at: `{report.generated_at}`",
        f"- Total observed file size: **{format_bytes(report.total_observed_bytes)}**",
        f"- Included targets: **{len(report.included_targets)}**",
        "",
        "## Category Summary",
        "",
    ]

    if report.category_summaries:
        lines.extend(
            [
                "| Category | Review guidance | Total size | Item count |",
                "| --- | --- | ---: | ---: |",
            ]
        )
        for summary in report.category_summaries:
            lines.append(
                f"| {summary.category_label} | `{summary.review_guidance}` | "
                f"{format_bytes(summary.total_size_bytes)} | {summary.item_count} |"
            )
    else:
        lines.append("No files were observed within the selected scan scope.")

    lines.extend(["", "## Top Directories", ""])
    lines.extend(_render_findings(report.top_directories))

    lines.extend(["", "## Top Files", ""])
    lines.extend(_render_findings(report.top_files))

    lines.extend(["", "## Unknown Large Items", ""])
    lines.extend(_render_findings(report.unknown_large_items))

    lines.extend(["", "## Limitations", ""])
    if report.limitations:
        for limitation in report.limitations:
            lines.append(
                f"- `{limitation.kind}` `{limitation.path}` - {limitation.message}"
            )
    else:
        lines.append("- No limitations were recorded.")

    lines.extend(["", "## Included Targets", ""])
    for target in report.included_targets:
        lines.append(f"- `{target.path}` - {target.description}")

    lines.append("")
    return "\n".join(lines)


def _record_top_finding(
    findings: list[ClassifiedFinding], finding: ClassifiedFinding, limit: int
) -> None:
    findings.append(finding)
    findings.sort(key=lambda item: (item.size_bytes, len(PurePosixPath(item.path).parts)), reverse=True)
    del findings[limit:]


def _build_directory_candidates(snapshot: ScanSnapshot) -> list[ClassifiedFinding]:
    target_roots = {
        target.name: PurePosixPath(target.path)
        for target in snapshot.included_targets
    }
    directory_sizes = dict(snapshot.directory_sizes)
    directory_targets = dict(snapshot.directory_targets)

    for partial_path in snapshot.partial_directories:
        directory_sizes.setdefault(partial_path, 0)
        if partial_path not in directory_targets:
            target_name = _find_target_name_for_path(PurePosixPath(partial_path), target_roots)
            if target_name is not None:
                directory_targets[partial_path] = target_name

    findings: list[ClassifiedFinding] = []
    for directory_path, size_bytes in directory_sizes.items():
        target_name = directory_targets.get(directory_path)
        if target_name is None:
            continue
        if size_bytes == 0:
            continue

        observed = ObservedEntry(
            path=directory_path,
            size_bytes=size_bytes,
            entry_type="directory",
            target_name=target_name,
            is_partial=directory_path in snapshot.partial_directories,
        )
        findings.append(classify_entry(observed))

    findings.sort(
        key=lambda item: (item.size_bytes, len(PurePosixPath(item.path).parts)),
        reverse=True,
    )
    return findings


def _find_target_name_for_path(
    path: PurePosixPath, target_roots: dict[str, PurePosixPath]
) -> str | None:
    for target_name, target_root in target_roots.items():
        if _is_same_or_child(path, target_root):
            return target_name
    return None


def _collapse_overlapping_directories(
    findings: list[ClassifiedFinding],
) -> list[ClassifiedFinding]:
    collapsed: list[ClassifiedFinding] = []

    for finding in findings:
        finding_path = PurePosixPath(finding.path)
        if any(_paths_overlap(finding_path, PurePosixPath(existing.path)) for existing in collapsed):
            continue
        collapsed.append(finding)

    return collapsed


def _suppress_target_roots(
    findings: list[ClassifiedFinding], included_targets: list
) -> list[ClassifiedFinding]:
    target_root_strings = {target.name: target.path for target in included_targets}
    child_survivors = {
        target_name: any(
            finding.target_name == target_name and finding.path != target_root
            for finding in findings
        )
        for target_name, target_root in target_root_strings.items()
    }

    return [
        finding
        for finding in findings
        if not (
            finding.path == target_root_strings.get(finding.target_name)
            and child_survivors.get(finding.target_name)
        )
    ]


def _paths_overlap(left: PurePosixPath, right: PurePosixPath) -> bool:
    return _is_same_or_child(left, right) or _is_same_or_child(right, left)


def _is_same_or_child(path: PurePosixPath, root: PurePosixPath) -> bool:
    return path == root or root in path.parents


def _render_findings(findings: list[ClassifiedFinding]) -> list[str]:
    if not findings:
        return ["No findings met the current reporting threshold."]

    lines: list[str] = []
    for finding in findings:
        lines.append(
            f"- **{format_bytes(finding.size_bytes)}** `{finding.path}` "
            f"({finding.category_label}, `{finding.review_guidance}`)"
        )
        lines.append(f"  - {finding.explanation}")
        if finding.is_partial:
            lines.append("  - Partial scan: one or more descendants could not be fully inspected.")
    return lines


def format_bytes(size_bytes: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(size_bytes)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024

    return f"{size_bytes} B"
