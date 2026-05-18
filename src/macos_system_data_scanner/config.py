from __future__ import annotations

from pathlib import Path

from macos_system_data_scanner.models import ObservationLimit, ScanOptions, ScanTarget

DEFAULT_OPTIONS = ScanOptions()
DEFAULT_JSON_REPORT = "system_scan_report/system-data-report.json"
DEFAULT_MARKDOWN_REPORT = "system_scan_report/system-data-report.md"


def default_scan_targets() -> list[ScanTarget]:
    home = Path.home()
    return [
        ScanTarget(
            name="user-caches",
            path=str(home / "Library" / "Caches"),
            description="User cache files.",
        ),
        ScanTarget(
            name="user-logs",
            path=str(home / "Library" / "Logs"),
            description="User log files.",
        ),
        ScanTarget(
            name="app-support",
            path=str(home / "Library" / "Application Support"),
            description="Application support data, including device backups.",
        ),
        ScanTarget(
            name="developer",
            path=str(home / "Library" / "Developer"),
            description="Developer tooling data such as Xcode and simulators.",
        ),
        ScanTarget(
            name="containers",
            path=str(home / "Library" / "Containers"),
            description="Per-app container storage.",
        ),
        ScanTarget(
            name="group-containers",
            path=str(home / "Library" / "Group Containers"),
            description="Shared app group container storage.",
        ),
        ScanTarget(
            name="messages",
            path=str(home / "Library" / "Messages"),
            description="Messages databases and attachments.",
        ),
        ScanTarget(
            name="mail",
            path=str(home / "Library" / "Mail"),
            description="Mail data and attachments.",
        ),
        ScanTarget(
            name="system-caches",
            path="/Library/Caches",
            description="System-wide cache files.",
        ),
        ScanTarget(
            name="system-logs",
            path="/Library/Logs",
            description="System-wide log files.",
        ),
        ScanTarget(
            name="var-logs",
            path="/private/var/log",
            description="macOS log files under /private/var/log.",
        ),
    ]


def not_directly_observable_limits() -> list[ObservationLimit]:
    return [
        ObservationLimit(
            kind="not-directly-observable",
            path="apfs://local-snapshots",
            message=(
                "APFS local snapshots can contribute to System Data, but they are not fully "
                "enumerated through this filesystem scan."
            ),
        ),
        ObservationLimit(
            kind="not-directly-observable",
            path="apfs://purgeable-space",
            message=(
                "Purgeable and other transient system-managed storage may affect the macOS "
                "System Data total without appearing as ordinary files."
            ),
        ),
    ]
