from __future__ import annotations

import argparse
from pathlib import Path

from macos_system_data_scanner.config import (
    DEFAULT_JSON_REPORT,
    DEFAULT_MARKDOWN_REPORT,
    DEFAULT_OPTIONS,
    default_scan_targets,
)
from macos_system_data_scanner.models import ScanOptions
from macos_system_data_scanner.reports import build_report, write_json_report, write_markdown_report
from macos_system_data_scanner.scanner import scan_targets


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scan common macOS System Data hotspots and generate JSON plus Markdown reports."
    )
    parser.add_argument(
        "--json-output",
        default=DEFAULT_JSON_REPORT,
        help=f"Path for the JSON report (default: {DEFAULT_JSON_REPORT}).",
    )
    parser.add_argument(
        "--markdown-output",
        default=DEFAULT_MARKDOWN_REPORT,
        help=f"Path for the Markdown report (default: {DEFAULT_MARKDOWN_REPORT}).",
    )
    parser.add_argument(
        "--top-directories",
        type=int,
        default=DEFAULT_OPTIONS.top_directories,
        help=f"Number of directories to include in the report (default: {DEFAULT_OPTIONS.top_directories}).",
    )
    parser.add_argument(
        "--top-files",
        type=int,
        default=DEFAULT_OPTIONS.top_files,
        help=f"Number of files to include in the report (default: {DEFAULT_OPTIONS.top_files}).",
    )
    parser.add_argument(
        "--min-size-mb",
        type=float,
        default=DEFAULT_OPTIONS.minimum_report_size_bytes / (1024 * 1024),
        help="Minimum size in MB for ranked report sections.",
    )
    parser.add_argument(
        "--stale-days",
        type=int,
        default=DEFAULT_OPTIONS.stale_threshold_days,
        help=f"Days since last modification before an item is considered stale (default: {DEFAULT_OPTIONS.stale_threshold_days}).",
    )
    return parser


def _progress(event: str, name: str, path: str) -> None:
    if event == "start":
        print(f"  Scanning  [{name}] {path} ...", flush=True)
    elif event == "done":
        print(f"  ✓ Done     [{name}]", flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.top_directories <= 0 or args.top_files <= 0:
        parser.error("--top-directories and --top-files must be positive integers.")
    if args.min_size_mb < 0:
        parser.error("--min-size-mb must be zero or greater.")
    if args.stale_days <= 0:
        parser.error("--stale-days must be a positive integer.")

    options = ScanOptions(
        top_directories=args.top_directories,
        top_files=args.top_files,
        minimum_report_size_bytes=int(args.min_size_mb * 1024 * 1024),
        stale_threshold_days=args.stale_days,
    )

    print("Starting macOS System Data scan...", flush=True)
    snapshot = scan_targets(default_scan_targets(), options, progress_callback=_progress)

    print("Generating report...", flush=True)
    report = build_report(snapshot, options)

    json_output = Path(args.json_output)
    markdown_output = Path(args.markdown_output)
    write_json_report(report, json_output)
    write_markdown_report(report, markdown_output)

    print("Scan complete.")
    print(f"JSON report: {json_output.resolve()}")
    print(f"Markdown report: {markdown_output.resolve()}")
    print(f"Observed categories: {len(report.category_summaries)}")
    print(f"Recorded limitations: {len(report.limitations)}")
    return 0
