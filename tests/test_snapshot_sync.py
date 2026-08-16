from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


KIT = Path(__file__).parents[1]
SCRIPT = KIT / "coletando-documentacao-tdn-protheus" / "scripts" / "sync_tdn_snapshot.py"


def load_module():
    if not SCRIPT.is_file():
        raise AssertionError(f"script ausente: {SCRIPT}")
    spec = importlib.util.spec_from_file_location("sync_tdn_snapshot", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


class SnapshotSyncTests(unittest.TestCase):
    def test_cli_exposes_snapshot_refresh_export_status_and_offline(self) -> None:
        result = subprocess.run([sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        for option in ("snapshot", "refresh", "export", "status", "--offline", "--dry-run"):
            self.assertIn(option, result.stdout)
        snapshot_help = subprocess.run([sys.executable, str(SCRIPT), "snapshot", "--help"], capture_output=True, text=True, check=False)
        self.assertEqual(snapshot_help.returncode, 0, snapshot_help.stderr + snapshot_help.stdout)
        self.assertIn("--resume", snapshot_help.stdout)

    def test_export_offline_reads_only_active_cached_pages(self) -> None:
        sync = load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            store = sync.SnapshotStore(Path(temp_dir), 235312129)
            active = sync.page_record(1, "Ativa", "https://tdn.totvs.com/a", "texto útil " * 8, 120, 3, "2026-01-01")
            removed = sync.page_record(2, "Removida", "https://tdn.totvs.com/b", "texto removido " * 8, 140, 1, "2025-01-01")
            removed["status"] = "removed"
            store.write_page(active)
            store.write_page(removed)
            manifest = sync.new_manifest(235312129, 8, 0.35)
            manifest["pages"] = {"1": sync.page_summary(active), "2": sync.page_summary(removed)}
            store.write_manifest(manifest)
            output = Path(temp_dir) / "export"
            with patch.object(sync, "TDNCollector", side_effect=AssertionError("offline fez HTTP")):
                count = sync.export_offline(store, output)
            pages = json.loads((output / "tdn_pages.json").read_text(encoding="utf-8"))
            self.assertEqual(count, 1)
            self.assertEqual([page["id"] for page in pages], [1])
            self.assertTrue((output / "tdn_pages.jsonl").read_text(encoding="utf-8").strip())

    def test_version_comparison_skips_unchanged_body_and_detects_change(self) -> None:
        sync = load_module()
        summary = {"version_number": 7, "version_when": "2026-01-01T12:00:00.000-03:00"}
        self.assertFalse(sync.page_changed(summary, {"number": 7, "when": "2026-01-01T12:00:00.000-03:00"}))
        self.assertTrue(sync.page_changed(summary, {"number": 8, "when": "2026-01-01T12:00:00.000-03:00"}))

    def test_partial_run_state_does_not_publish_manifest(self) -> None:
        sync = load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            store = sync.SnapshotStore(Path(temp_dir), 235312129)
            store.write_state({"root_id": 235312129, "pending_ids": [1, 2], "completed_ids": []})
            self.assertIsNone(store.load_manifest())
            self.assertEqual(store.load_state()["pending_ids"], [1, 2])

    def test_refresh_reuses_unchanged_page_without_fetching_body(self) -> None:
        sync_module = load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            store = sync_module.SnapshotStore(Path(temp_dir), 235312129)
            record = sync_module.page_record(1, "Ativa", "https://tdn.totvs.com/a", "texto útil " * 8, 120, 3, "2026-01-01")
            store.write_page(record)
            manifest = sync_module.new_manifest(235312129, 8, 0)
            manifest["pages"] = {"1": sync_module.page_summary(record)}
            store.write_manifest(manifest)
            synchronizer = sync_module.SnapshotSynchronizer(235312129, Path(temp_dir), 0)
            synchronizer.discover_tree = lambda _depth, _limit: [1]
            synchronizer.fetch_version = lambda _page_id: {"number": 3, "when": "2026-01-01"}
            synchronizer.fetch_page = lambda _page_id: self.fail("corpo de página inalterada foi baixado")
            result = synchronizer.refresh(8, None)
            self.assertEqual(result["unchanged"], 1)

    def test_refresh_marks_missing_page_removed(self) -> None:
        sync_module = load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            store = sync_module.SnapshotStore(Path(temp_dir), 235312129)
            record = sync_module.page_record(2, "Antiga", "https://tdn.totvs.com/b", "texto útil " * 8, 120, 1, "2025-01-01")
            store.write_page(record)
            manifest = sync_module.new_manifest(235312129, 8, 0)
            manifest["pages"] = {"2": sync_module.page_summary(record)}
            store.write_manifest(manifest)
            synchronizer = sync_module.SnapshotSynchronizer(235312129, Path(temp_dir), 0)
            synchronizer.discover_tree = lambda _depth, _limit: []
            result = synchronizer.refresh(8, None)
            self.assertEqual(result["removed"], 1)
            self.assertEqual(store.load_manifest()["pages"]["2"]["status"], "removed")

    def test_discovery_respects_max_pages_without_publishing_snapshot(self) -> None:
        sync_module = load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            synchronizer = sync_module.SnapshotSynchronizer(235312129, Path(temp_dir), 0)
            synchronizer.collector.list_children = lambda _page_id: [{"id": "2"}]
            with self.assertRaises(sync_module.PageLimitReached):
                synchronizer.discover_tree(8, 1)
            self.assertIsNone(synchronizer.store.load_manifest())

    def test_dry_run_returns_a_partial_estimate_when_the_page_limit_is_reached(self) -> None:
        sync_module = load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            synchronizer = sync_module.SnapshotSynchronizer(235312129, Path(temp_dir), 0)
            synchronizer.collector.list_children = lambda _page_id: [{"id": "2"}]

            result = synchronizer.snapshot(8, 1, 1, True, False)

            self.assertEqual(result["mode"], "dry-run")
            self.assertFalse(result["complete"])
            self.assertEqual(result["stop_reason"], "max-pages")
            self.assertEqual(result["pages_discovered"], 1)
            self.assertIsNone(synchronizer.store.load_manifest())

    def test_dry_run_returns_a_partial_estimate_when_the_duration_expires(self) -> None:
        sync_module = load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            synchronizer = sync_module.SnapshotSynchronizer(235312129, Path(temp_dir), 0)
            with patch.object(sync_module.time, "monotonic", side_effect=(0, 2)):
                result = synchronizer.snapshot(8, None, 1, True, False, max_duration_seconds=1)

            self.assertEqual(result["mode"], "dry-run")
            self.assertFalse(result["complete"])
            self.assertEqual(result["stop_reason"], "max-duration")
            self.assertEqual(result["pages_discovered"], 0)

    def test_resume_finishes_partial_snapshot_and_publishes_once_complete(self) -> None:
        sync_module = load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            store = sync_module.SnapshotStore(Path(temp_dir), 235312129)
            store.write_state({
                "root_id": 235312129, "max_depth": 8, "delay_seconds": 0,
                "pending_ids": [1], "completed_ids": [], "pages": {}, "started_at": "2026-01-01T00:00:00+00:00",
            })
            synchronizer = sync_module.SnapshotSynchronizer(235312129, Path(temp_dir), 0)
            synchronizer.fetch_page = lambda _page_id: sync_module.page_record(1, "Ativa", "https://tdn.totvs.com/a", "texto útil " * 8, 120, 1, "2026-01-01")
            result = synchronizer.snapshot(8, None, 1, False, True)
            self.assertEqual(result["pages_saved"], 1)
            self.assertEqual(store.load_manifest()["pages"]["1"]["status"], "active")
            self.assertIsNone(store.load_state())

    def test_refresh_failure_preserves_last_complete_manifest(self) -> None:
        sync_module = load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            store = sync_module.SnapshotStore(Path(temp_dir), 235312129)
            record = sync_module.page_record(1, "Ativa", "https://tdn.totvs.com/a", "texto útil " * 8, 120, 1, "2025-01-01")
            store.write_page(record)
            manifest = sync_module.new_manifest(235312129, 8, 0)
            manifest["pages"] = {"1": sync_module.page_summary(record)}
            store.write_manifest(manifest)
            synchronizer = sync_module.SnapshotSynchronizer(235312129, Path(temp_dir), 0)
            synchronizer.discover_tree = lambda _depth, _limit: [1]
            synchronizer.fetch_version = lambda _page_id: {"number": 2, "when": "2026-01-01"}
            synchronizer.fetch_page = lambda _page_id: (_ for _ in ()).throw(RuntimeError("rede caiu"))
            with self.assertRaisesRegex(RuntimeError, "rede caiu"):
                synchronizer.refresh(8, None)
            self.assertEqual(store.load_manifest()["pages"]["1"]["version_number"], 1)

    def test_refresh_marks_page_removed_when_version_lookup_returns_404(self) -> None:
        sync_module = load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            store = sync_module.SnapshotStore(Path(temp_dir), 235312129)
            record = sync_module.page_record(1, "Ativa", "https://tdn.totvs.com/a", "texto útil " * 8, 120, 1, "2025-01-01")
            store.write_page(record)
            manifest = sync_module.new_manifest(235312129, 8, 0)
            manifest["pages"] = {"1": sync_module.page_summary(record)}
            store.write_manifest(manifest)
            synchronizer = sync_module.SnapshotSynchronizer(235312129, Path(temp_dir), 0)
            synchronizer.discover_tree = lambda _depth, _limit: [1]
            synchronizer.fetch_version = lambda _page_id: None
            result = synchronizer.refresh(8, None)
            self.assertEqual(result["removed"], 1)
            self.assertEqual(store.load_manifest()["pages"]["1"]["status"], "removed")


if __name__ == "__main__":
    unittest.main()
