from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from macos_system_data_scanner.models import ScanOptions, ScanTarget
from macos_system_data_scanner.reports import build_report, render_markdown_report, write_json_report
from macos_system_data_scanner.scanner import _disk_usage_bytes, scan_targets


def write_bytes(path: Path, size: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)


class ScannerTests(unittest.TestCase):
    def test_missing_target_is_recorded_without_aborting(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            existing = Path(tmpdir) / "Library" / "Caches"
            existing.mkdir(parents=True)
            write_bytes(existing / "cache.bin", 8)

            snapshot = scan_targets(
                [
                    ScanTarget("existing", str(existing), "Existing target"),
                    ScanTarget("missing", str(Path(tmpdir) / "missing"), "Missing target"),
                ],
                ScanOptions(top_directories=5, top_files=5, minimum_report_size_bytes=0),
            )

        limitation_kinds = {limit.kind for limit in snapshot.limitations}
        self.assertIn("unavailable-target", limitation_kinds)
        self.assertEqual(1, len(snapshot.included_targets))
        self.assertTrue(snapshot.entries)

    def test_ranking_and_category_summaries_are_generated(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            caches = base / "Library" / "Caches"
            mail = base / "Library" / "Mail"
            write_bytes(caches / "big-cache.bin", 12)
            write_bytes(mail / "message.emlx", 5)
            expected_cache_size = _disk_usage_bytes((caches / "big-cache.bin").stat())

            report = build_report(
                scan_targets(
                    [
                        ScanTarget("caches", str(caches), "Caches"),
                        ScanTarget("mail", str(mail), "Mail"),
                    ],
                    ScanOptions(top_directories=5, top_files=5, minimum_report_size_bytes=0),
                ),
                ScanOptions(top_directories=5, top_files=5, minimum_report_size_bytes=0),
            )

        self.assertEqual(str(caches), report.top_directories[0].path)
        self.assertEqual(str(caches / "big-cache.bin"), report.top_files[0].path)
        self.assertEqual("Caches", report.category_summaries[0].category_label)
        self.assertEqual(expected_cache_size, report.category_summaries[0].total_size_bytes)

    def test_permission_failures_are_preserved_as_limitations(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            blocked = base / "blocked"
            blocked.mkdir()
            real_scandir = os.scandir

            def guarded_scandir(path: os.PathLike[str] | str):
                if Path(path) == blocked:
                    raise PermissionError("no access")
                return real_scandir(path)

            with patch("macos_system_data_scanner.scanner.os.scandir", side_effect=guarded_scandir):
                snapshot = scan_targets(
                    [ScanTarget("root", str(base), "Root")],
                    ScanOptions(top_directories=5, top_files=5, minimum_report_size_bytes=0),
                )
                report = build_report(
                    snapshot,
                    ScanOptions(top_directories=5, top_files=5, minimum_report_size_bytes=0),
                )

        self.assertTrue(
            any(limit.kind == "permission-denied" and limit.path == str(blocked) for limit in snapshot.limitations)
        )
        self.assertNotIn(str(blocked), [finding.path for finding in report.top_directories])
        self.assertFalse(report.top_directories)

    def test_json_and_markdown_reports_share_the_same_ranked_findings(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            developer = base / "Library" / "Developer" / "Xcode" / "DerivedData"
            write_bytes(developer / "archive.data", 16)

            report = build_report(
                scan_targets(
                    [ScanTarget("developer", str(base / "Library" / "Developer"), "Developer")],
                    ScanOptions(top_directories=5, top_files=5, minimum_report_size_bytes=0),
                ),
                ScanOptions(top_directories=5, top_files=5, minimum_report_size_bytes=0),
            )

            json_path = base / "report.json"
            write_json_report(report, json_path)
            markdown = render_markdown_report(report)
            payload = json.loads(json_path.read_text(encoding="utf-8"))

        self.assertEqual(report.top_files[0].path, payload["top_files"][0]["path"])
        self.assertIn(report.top_files[0].path, markdown)
        self.assertIn(report.category_summaries[0].category_label, markdown)

    def test_unknown_items_and_not_directly_observable_limits_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            weird = base / "WeirdStorage"
            write_bytes(weird / "mystery.bin", 7)

            report = build_report(
                scan_targets(
                    [ScanTarget("weird", str(weird), "Weird")],
                    ScanOptions(top_directories=5, top_files=5, minimum_report_size_bytes=0),
                ),
                ScanOptions(top_directories=5, top_files=5, minimum_report_size_bytes=0),
            )

        self.assertEqual("unknown", report.unknown_large_items[0].category)
        self.assertTrue(
            any(limit.kind == "not-directly-observable" for limit in report.limitations)
        )

    def test_classification_respects_path_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            confusing = base / "Library" / "CachesBackup"
            write_bytes(confusing / "archive.bin", 11)

            report = build_report(
                scan_targets(
                    [ScanTarget("confusing", str(confusing), "Confusing")],
                    ScanOptions(top_directories=5, top_files=5, minimum_report_size_bytes=0),
                ),
                ScanOptions(top_directories=5, top_files=5, minimum_report_size_bytes=0),
            )

        self.assertEqual("unknown", report.top_files[0].category)

    def test_unsupported_filesystem_entries_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            fifo_path = base / "pipe"
            os.mkfifo(fifo_path)

            snapshot = scan_targets(
                [ScanTarget("root", str(base), "Root")],
                ScanOptions(top_directories=5, top_files=5, minimum_report_size_bytes=0),
            )

        self.assertTrue(
            any(limit.kind == "scan-error" and limit.path == str(fifo_path) for limit in snapshot.limitations)
        )

    def test_disk_usage_prefers_allocated_blocks(self) -> None:
        stat_result = SimpleNamespace(st_blocks=3, st_size=10_000)
        self.assertEqual(1536, _disk_usage_bytes(stat_result))

    def test_hard_links_are_not_double_counted(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            storage = base / "Library" / "Application Support"
            original = storage / "blob.bin"
            linked = storage / "blob-link.bin"
            write_bytes(original, 32)
            os.link(original, linked)
            expected_size = _disk_usage_bytes(original.stat())

            report = build_report(
                scan_targets(
                    [ScanTarget("support", str(storage), "Support")],
                    ScanOptions(top_directories=5, top_files=5, minimum_report_size_bytes=0),
                ),
                ScanOptions(top_directories=5, top_files=5, minimum_report_size_bytes=0),
            )

        self.assertEqual(expected_size, report.total_observed_bytes)
        self.assertEqual(1, len(report.top_files))

    def test_top_directories_prefer_actionable_nested_hotspots(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            target = base / "Library" / "Application Support"
            hotspot = target / "BigApp" / "Cache"
            other = target / "SmallApp"
            write_bytes(hotspot / "big.bin", 64)
            write_bytes(other / "small.bin", 8)

            report = build_report(
                scan_targets(
                    [ScanTarget("support", str(target), "Support")],
                    ScanOptions(top_directories=5, top_files=5, minimum_report_size_bytes=0),
                ),
                ScanOptions(top_directories=5, top_files=5, minimum_report_size_bytes=0),
            )

        self.assertEqual(str(hotspot), report.top_directories[0].path)

    def test_duplicate_target_names_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            target = base / "Library" / "Caches"
            target.mkdir(parents=True)

            with self.assertRaises(ValueError):
                scan_targets(
                    [
                        ScanTarget("dup", str(target), "First"),
                        ScanTarget("dup", str(target), "Second"),
                    ],
                    ScanOptions(top_directories=5, top_files=5, minimum_report_size_bytes=0),
                )


    def test_stale_items_are_identified_correctly(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            target = base / "Library" / "Caches"
            write_bytes(target / "fresh.bin", 1024 * 1024)
            write_bytes(target / "old.bin", 2 * 1024 * 1024)

            old_path = target / "old.bin"
            old_epoch = 0.0  # Unix epoch = many years ago
            os.utime(old_path, (old_epoch, old_epoch))

            options = ScanOptions(
                top_directories=5,
                top_files=5,
                minimum_report_size_bytes=0,
                stale_threshold_days=365,
            )
            report = build_report(
                scan_targets([ScanTarget("caches", str(target), "Caches")], options),
                options,
            )

        stale_paths = {f.path for f in report.stale_large_items}
        self.assertIn(str(old_path), stale_paths)
        self.assertNotIn(str(target / "fresh.bin"), stale_paths)


if __name__ == "__main__":
    unittest.main()
