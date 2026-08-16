from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import importlib.util
import sys

KIT = Path(__file__).parents[1]
SCRIPT = KIT / "coletando-documentacao-tdn-protheus" / "scripts" / "sync_tdn_snapshot.py"


def load_module():
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
    def test_v1_snapshot_is_readable_and_exportable(self) -> None:
        sync = load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            store = sync.SnapshotStore(Path(temp_dir), 1)
            pages = store.root / "pages"
            pages.mkdir(parents=True)
            (pages / "10.json").write_text(json.dumps({"id": 10, "title": "A", "url": "https://tdn/a", "text": "texto útil " * 8, "body_len": 100}), encoding="utf-8")
            sync.write_json_atomic(store.manifest_path, {"schema_version": 1, "root_id": 1, "pages": {"10": {"status": "active"}}})
            output = Path(temp_dir) / "out"
            self.assertEqual(sync.export_offline(store, output), 1)
            self.assertEqual(json.loads((output / "tdn_pages.json").read_text())[0]["id"], 10)

    def test_snapshot_publishes_generation_v2_atomically(self) -> None:
        sync = load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            worker = sync.SnapshotSynchronizer(999, Path(temp_dir), 0)
            worker.collector.list_children = lambda _id: self.fail("não deve listar filhos")
            worker.fetch_page = lambda page_id: sync.page_record(page_id, "MATA103", "https://tdn/mata103", "texto útil " * 8, 100, 1, "2026")
            result = worker.snapshot(0, None, 1, False, False)
            manifest = worker.store.load_manifest()
            self.assertEqual(result["pages_saved"], 1)
            self.assertEqual(manifest["schema_version"], 2)
            self.assertTrue(manifest["page_directory"].startswith("generations/"))
            self.assertTrue((worker.store.pages_dir(manifest) / "999.json").is_file())
            self.assertFalse((worker.store.root / "pages" / "999.json").exists())

    def test_refresh_failure_preserves_manifest_and_active_page_bytes(self) -> None:
        sync = load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            worker = sync.SnapshotSynchronizer(1, Path(temp_dir), 0)
            worker.collector.list_children = lambda _id: []
            worker.fetch_page = lambda page_id: sync.page_record(page_id, "Original", "https://tdn/1", "original " * 20, 100, 1, "old")
            worker.snapshot(0, None, 1, False, False)
            before_manifest = worker.store.manifest_path.read_bytes()
            before = worker.store.read_page(1)["text"]
            worker.discover_tree = lambda _depth, _limit: [1, 2]
            worker.fetch_version = lambda _id: {"number": 2, "when": "new"}
            calls = {"n": 0}
            def fetch(page_id):
                calls["n"] += 1
                if calls["n"] == 2:
                    raise RuntimeError("rede caiu")
                return sync.page_record(page_id, "Nova", f"https://tdn/{page_id}", "novo " * 20, 120, 2, "new")
            worker.fetch_page = fetch
            with self.assertRaisesRegex(RuntimeError, "rede caiu"):
                worker.refresh(1, None)
            self.assertEqual(worker.store.manifest_path.read_bytes(), before_manifest)
            self.assertEqual(worker.store.read_page(1)["text"], before)

    def test_refresh_from_v1_migrates_to_v2_and_copies_unchanged_page(self) -> None:
        sync = load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            store = sync.SnapshotStore(Path(temp_dir), 1)
            pages = store.root / "pages"
            pages.mkdir(parents=True)
            record = sync.page_record(1, "A", "https://tdn/a", "texto útil " * 8, 100, 1, "same")
            sync.write_json_atomic(pages / "1.json", record)
            sync.write_json_atomic(store.manifest_path, {"schema_version": 1, "root_id": 1, "created_at": "old", "pages": {"1": sync.page_summary(record)}})
            worker = sync.SnapshotSynchronizer(1, Path(temp_dir), 0)
            worker.discover_tree = lambda _depth, _limit: [1]
            worker.fetch_version = lambda _id: {"number": 1, "when": "same"}
            worker.fetch_page = lambda _id: self.fail("não deve baixar corpo inalterado")
            result = worker.refresh(1, None)
            manifest = store.load_manifest()
            self.assertEqual(result["unchanged"], 1)
            self.assertEqual(manifest["schema_version"], 2)
            self.assertEqual(store.read_page(1, manifest)["text"], record["text"])

    def test_changed_page_below_minimum_becomes_filtered_not_stale(self) -> None:
        sync = load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            worker = sync.SnapshotSynchronizer(1, Path(temp_dir), 0)
            worker.collector.list_children = lambda _id: []
            worker.fetch_page = lambda page_id: sync.page_record(page_id, "A", "https://tdn/a", "texto útil " * 8, 100, 1, "old")
            worker.snapshot(0, None, 1, False, False)
            worker.discover_tree = lambda _depth, _limit: [1]
            worker.fetch_version = lambda _id: {"number": 2, "when": "new"}
            worker.fetch_page = lambda page_id: sync.page_record(page_id, "A", "https://tdn/a", "stub", 4, 2, "new")
            result = worker.refresh(0, None)
            manifest = worker.store.load_manifest()
            self.assertEqual(result["filtered"], 1)
            self.assertEqual(manifest["pages"]["1"]["status"], "filtered")
            self.assertFalse((worker.store.pages_dir(manifest) / "1.json").exists())

    def test_lock_rejects_second_writer(self) -> None:
        sync = load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "1"
            with sync.SnapshotLock(root):
                with self.assertRaisesRegex(RuntimeError, "outra atualização"):
                    with sync.SnapshotLock(root):
                        pass

    def test_dry_run_is_bounded_and_never_publishes(self) -> None:
        sync = load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            worker = sync.SnapshotSynchronizer(1, Path(temp_dir), 1)
            worker.collector.list_children = lambda _id: []
            clock = [0.0]
            def monotonic(): return clock[0]
            def sleep(seconds): clock[0] += seconds
            with patch.object(sync.time, "monotonic", monotonic), patch.object(sync.time, "sleep", sleep):
                result = worker.snapshot(0, None, 1, True, False, max_duration_seconds=0.1)
            self.assertFalse(result["complete"])
            self.assertEqual(result["stop_reason"], "max-duration")
            self.assertIsNone(worker.store.load_manifest())

    def test_resume_uses_same_staging_generation(self) -> None:
        sync = load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            store = sync.SnapshotStore(Path(temp_dir), 1)
            run_id = "resume-test"
            (store.staging_dir(run_id) / "pages").mkdir(parents=True)
            store.write_state({"mode": "snapshot", "run_id": run_id, "root_id": 1, "max_depth": 0, "delay_seconds": 0, "pending_ids": [1], "completed_ids": [], "pages": {}, "started_at": "2026-01-01T00:00:00+00:00"})
            worker = sync.SnapshotSynchronizer(1, Path(temp_dir), 0)
            worker.fetch_page = lambda page_id: sync.page_record(page_id, "A", "https://tdn/a", "texto útil " * 8, 100, 1, "x")
            worker.snapshot(0, None, 1, False, True)
            manifest = store.load_manifest()
            self.assertEqual(manifest["generation_id"], run_id)
            self.assertIsNone(store.load_state())


if __name__ == "__main__":
    unittest.main()
