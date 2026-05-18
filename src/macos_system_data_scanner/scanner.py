from __future__ import annotations

import os
import stat
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path

from macos_system_data_scanner.classifier import classify_entry
from macos_system_data_scanner.config import not_directly_observable_limits
from macos_system_data_scanner.models import (
    ObservationLimit,
    ObservedEntry,
    ScanOptions,
    ScanSnapshot,
    ScanTarget,
)

MAX_RECORDED_LIMITATIONS = 500


def scan_targets(
    targets: list[ScanTarget],
    options: ScanOptions | None = None,
    progress_callback: Callable[[str, str, str], None] | None = None,
) -> ScanSnapshot:
    options = options or ScanOptions(minimum_report_size_bytes=0)
    snapshot = ScanSnapshot(category_totals=defaultdict(lambda: {"total_size_bytes": 0, "item_count": 0}))
    seen_file_inodes: set[tuple[int, int]] = set()
    _validate_unique_target_names(targets)

    for target in targets:
        target_path = Path(target.path).expanduser()
        if progress_callback:
            progress_callback("start", target.name, str(target_path))
        normalized_target = ScanTarget(
            name=target.name,
            path=str(target_path),
            description=target.description,
        )

        try:
            target_stat = target_path.stat(follow_symlinks=False)
        except FileNotFoundError:
            _record_limitation(
                snapshot,
                ObservationLimit(
                    kind="unavailable-target",
                    path=str(target_path),
                    message="Configured scan target does not exist on this machine.",
                )
            )
            continue
        except PermissionError:
            snapshot.included_targets.append(normalized_target)
            _record_limitation(
                snapshot,
                ObservationLimit(
                    kind="permission-denied",
                    path=str(target_path),
                    message="Permission denied while probing this configured scan target.",
                )
            )
            continue
        except OSError as error:
            snapshot.included_targets.append(normalized_target)
            _record_limitation(
                snapshot,
                ObservationLimit(
                    kind="scan-error",
                    path=str(target_path),
                    message=f"Failed to probe configured scan target: {error}",
                )
            )
            continue

        snapshot.included_targets.append(normalized_target)

        if target_path.is_symlink():
            _record_limitation(
                snapshot,
                ObservationLimit(
                    kind="skipped-symlink",
                    path=str(target_path),
                    message="Configured scan target is a symlink and was skipped to avoid duplicate traversal.",
                )
            )
            continue

        if stat.S_ISREG(target_stat.st_mode):
            inode_key = (target_stat.st_dev, target_stat.st_ino)
            if inode_key in seen_file_inodes:
                continue

            seen_file_inodes.add(inode_key)
            _record_file_entry(
                snapshot,
                ObservedEntry(
                    path=str(target_path),
                    size_bytes=_disk_usage_bytes(target_stat),
                    entry_type="file",
                    target_name=target.name,
                ),
                Path(target.path).expanduser(),
                options,
            )
            continue

        if not stat.S_ISDIR(target_stat.st_mode):
            _record_limitation(
                snapshot,
                ObservationLimit(
                    kind="scan-error",
                    path=str(target_path),
                    message="Configured scan target is not a regular file or directory and was skipped.",
                )
            )
            continue

        _scan_directory(target_path, target.name, snapshot, seen_file_inodes, options, target_path)
        if progress_callback:
            progress_callback("done", target.name, str(target_path))

    for limitation in not_directly_observable_limits():
        _record_limitation(snapshot, limitation)
    if snapshot.omitted_limitations:
        snapshot.limitations.append(
            ObservationLimit(
                kind="truncated-limitations",
                path="summary://limitations",
                message=(
                    f"{snapshot.omitted_limitations} additional limitation entries were omitted "
                    f"after the first {MAX_RECORDED_LIMITATIONS} recorded paths."
                ),
            )
        )
    return snapshot


def _scan_directory(
    path: Path,
    target_name: str,
    snapshot: ScanSnapshot,
    seen_file_inodes: set[tuple[int, int]],
    options: ScanOptions,
    target_root: Path,
) -> None:
    try:
        with os.scandir(path) as iterator:
            for entry in iterator:
                child_path = Path(entry.path)
                if entry.is_symlink():
                    _record_limitation(
                        snapshot,
                        ObservationLimit(
                            kind="skipped-symlink",
                            path=str(child_path),
                            message="Symlink skipped to avoid recursive loops or duplicate accounting.",
                        )
                    )
                    continue

                try:
                    if entry.is_dir(follow_symlinks=False):
                        _scan_directory(
                            child_path,
                            target_name,
                            snapshot,
                            seen_file_inodes,
                            options,
                            target_root,
                        )
                    elif entry.is_file(follow_symlinks=False):
                        file_stat = entry.stat(follow_symlinks=False)
                        inode_key = (file_stat.st_dev, file_stat.st_ino)
                        if inode_key in seen_file_inodes:
                            continue

                        seen_file_inodes.add(inode_key)
                        _record_file_entry(
                            snapshot,
                            ObservedEntry(
                                path=str(child_path),
                                size_bytes=_disk_usage_bytes(file_stat),
                                entry_type="file",
                                target_name=target_name,
                            ),
                            target_root,
                            options,
                        )
                    else:
                        _mark_partial_directories(snapshot, child_path.parent, target_root)
                        _record_limitation(
                            snapshot,
                            ObservationLimit(
                                kind="scan-error",
                                path=str(child_path),
                                message="Unsupported filesystem entry type was skipped.",
                            )
                        )
                except PermissionError:
                    _mark_partial_directories(snapshot, child_path.parent, target_root)
                    _record_limitation(
                        snapshot,
                        ObservationLimit(
                            kind="permission-denied",
                            path=str(child_path),
                            message="Permission denied while inspecting this path.",
                        )
                    )
                except OSError as error:
                    _mark_partial_directories(snapshot, child_path.parent, target_root)
                    _record_limitation(
                        snapshot,
                        ObservationLimit(
                            kind="scan-error",
                            path=str(child_path),
                            message=f"Failed to inspect path: {error}",
                        )
                    )
    except PermissionError:
        _mark_partial_directories(snapshot, path, target_root)
        _record_limitation(
            snapshot,
            ObservationLimit(
                kind="permission-denied",
                path=str(path),
                message="Permission denied while listing this directory.",
            )
        )
        return
    except OSError as error:
        _mark_partial_directories(snapshot, path, target_root)
        _record_limitation(
            snapshot,
            ObservationLimit(
                kind="scan-error",
                path=str(path),
                message=f"Failed to list directory: {error}",
            )
        )
        return


def _disk_usage_bytes(stat_result: os.stat_result) -> int:
    blocks = getattr(stat_result, "st_blocks", 0)
    if blocks:
        return blocks * 512
    return stat_result.st_size


def _record_file_entry(
    snapshot: ScanSnapshot,
    entry: ObservedEntry,
    target_root: Path,
    options: ScanOptions,
) -> None:
    snapshot.total_observed_bytes += entry.size_bytes
    _aggregate_directory_sizes(snapshot, Path(entry.path), target_root, entry.target_name, entry.size_bytes)

    classified = classify_entry(entry)
    key = (
        classified.category,
        classified.category_label,
        classified.review_guidance,
    )
    if key not in snapshot.category_totals:
        snapshot.category_totals[key] = {"total_size_bytes": 0, "item_count": 0}
    snapshot.category_totals[key]["total_size_bytes"] += entry.size_bytes
    snapshot.category_totals[key]["item_count"] += 1

    if entry.size_bytes >= options.minimum_report_size_bytes:
        _record_top_entry(snapshot.entries, entry, options.top_files)
        if classified.category == "unknown":
            _record_top_entry(
                snapshot.unknown_entries,
                entry,
                max(options.top_directories, options.top_files),
            )


def _aggregate_directory_sizes(
    snapshot: ScanSnapshot,
    file_path: Path,
    target_root: Path,
    target_name: str,
    size_bytes: int,
) -> None:
    current = file_path.parent
    while current == target_root or target_root in current.parents:
        key = str(current)
        snapshot.directory_sizes[key] = snapshot.directory_sizes.get(key, 0) + size_bytes
        snapshot.directory_targets[key] = target_name
        if current == target_root:
            break
        current = current.parent


def _mark_partial_directories(snapshot: ScanSnapshot, path: Path, target_root: Path) -> None:
    current = path
    while current == target_root or target_root in current.parents:
        snapshot.partial_directories.add(str(current))
        if current == target_root:
            break
        current = current.parent


def _record_top_entry(entries: list[ObservedEntry], entry: ObservedEntry, limit: int) -> None:
    entries.append(entry)
    entries.sort(key=lambda item: (item.size_bytes, len(Path(item.path).parts)), reverse=True)
    del entries[limit:]


def _validate_unique_target_names(targets: list[ScanTarget]) -> None:
    seen_names: set[str] = set()
    for target in targets:
        if target.name in seen_names:
            raise ValueError(f"Duplicate scan target name: {target.name}")
        seen_names.add(target.name)


def _record_limitation(snapshot: ScanSnapshot, limitation: ObservationLimit) -> None:
    if len(snapshot.limitations) < MAX_RECORDED_LIMITATIONS:
        snapshot.limitations.append(limitation)
        return

    snapshot.omitted_limitations += 1
