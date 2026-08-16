from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

KIT = Path(__file__).parents[1]
SCRIPT = (
    KIT
    / "coletando-documentacao-tdn-protheus"
    / "scripts"
    / "sync_tdn_snapshot.py"
)


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


def record(sync, page_id: int, text: str = "texto útil " * 8, version: int = 1):
    return sync.page_record(
        page_id,
        f"Página {page_id}",
        f"https://tdn/{page_id}",
        text,
        len(text),
        version,
        f"v{version}",
    )


class SnapshotSyncTests(unittest.TestCase):
    def test_store_rejects_invalid_manifest_directory_and_resume_state(self) -> None:
        sync = load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            store = sync.SnapshotStore(Path(temp_dir), 1)
            store.root.mkdir(parents=True)
            store.manifest_path.write_text("[]", encoding="utf-8")
            with self.assertRaisesRegex(TypeError, "objeto JSON"):
                store.load_manifest()
            store.manifest_path.write_text(json.dumps({"pages": []}), encoding="utf-8")
            with self.assertRaisesRegex(TypeError, "pages"):
                store.load_manifest()
            store.manifest_path.write_text(json.dumps({"root_id": 2, "pages": {}}), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "root_id"):
                store.load_manifest()
            manifest = {"root_id": 1, "pages": {}, "page_directory": "../escape"}
            with self.assertRaisesRegex(RuntimeError, "fora da raiz"):
                store.pages_dir(manifest)
            for value in ("[]", "not-json"):
                store.state_path.write_text(value, encoding="utf-8")
                with self.assertRaises((TypeError, RuntimeError)):
                    store.load_state()

    def test_snapshot_filter_resume_invalid_and_status_v1_v2(self) -> None:
        sync = load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            worker = sync.SnapshotSynchronizer(1, Path(temp_dir), 0)
            worker.collector.list_children = lambda _page_id: []
            worker.fetch_page = lambda page_id: record(sync, page_id, text="stub")
            result = worker.snapshot(0, None, 1, False, False)
            self.assertEqual(result["filtered"], 1)
            manifest = worker.store.load_manifest()
            self.assertEqual(sync.status(worker.store)["schema_version"], 2)
            self.assertEqual(sync.status(worker.store)["active_pages"], 0)
            self.assertEqual(sync.export_offline(worker.store, Path(temp_dir) / "out"), 0)
            worker.store.write_state({"mode": "wrong", "run_id": "x", "root_id": 1})
            with self.assertRaisesRegex(RuntimeError, "não existe estado retomável"):
                worker.snapshot(0, None, 1, False, True)
            worker.store.clear_state()
            self.assertEqual(manifest["schema_version"], 2)

    def test_refresh_handles_removed_reactivated_and_multiple_pages(self) -> None:
        sync = load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            worker = sync.SnapshotSynchronizer(1, Path(temp_dir), 0)
            worker.discover_tree = lambda _depth, _limit: [1, 2]
            worker.fetch_page = lambda page_id: record(sync, page_id, version=1)
            worker.snapshot(1, None, 1, False, False)
            worker.discover_tree = lambda _depth, _limit: [1, 3]
            worker.fetch_version = lambda page_id: None if page_id == 1 else {"number": 2, "when": "v2"}
            worker.fetch_page = lambda page_id: record(sync, page_id, version=2)
            result = worker.refresh(1, None)
            manifest = worker.store.load_manifest()
            self.assertEqual(result["removed"], 2)
            self.assertEqual(manifest["pages"]["1"]["status"], "removed")
            self.assertEqual(manifest["pages"]["2"]["status"], "removed")
            self.assertEqual(manifest["pages"]["3"]["status"], "active")
            worker.discover_tree = lambda _depth, _limit: [1, 3]
            worker.fetch_version = lambda page_id: {"number": 3, "when": "v3"}
            worker.fetch_page = lambda page_id: record(sync, page_id, version=3)
            worker.refresh(1, None)
            self.assertEqual(worker.store.load_manifest()["pages"]["1"]["status"], "active")

    def test_publish_failure_and_generation_collision_do_not_replace_active_manifest(self) -> None:
        sync = load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            store = sync.SnapshotStore(Path(temp_dir), 1)
            run_id = "run"
            (store.staging_dir(run_id) / "pages").mkdir(parents=True)
            store.manifest_path.parent.mkdir(parents=True, exist_ok=True)
            store.manifest_path.write_bytes(b'{"old":true}')
            with (
                patch.object(sync, "write_json_atomic", side_effect=OSError("disk")),
                self.assertRaisesRegex(OSError, "disk"),
            ):
                store.publish(run_id, {"root_id": 1, "pages": {}})
            self.assertEqual(store.manifest_path.read_bytes(), b'{"old":true}')
            self.assertFalse((store.root / "generations" / run_id).exists())
            (store.staging_dir(run_id) / "pages").mkdir(parents=True)
            (store.root / "generations" / run_id).mkdir(parents=True)
            with self.assertRaisesRegex(RuntimeError, "generation_id"):
                store.publish(run_id, {"root_id": 1, "pages": {}})
    def test_v1_snapshot_is_readable_and_exportable(self) -> None:
        sync = load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            store = sync.SnapshotStore(Path(temp_dir), 1)
            pages = store.root / "pages"
            pages.mkdir(parents=True)
            (pages / "10.json").write_text(
                json.dumps(
                    {
                        "id": 10,
                        "title": "A",
                        "url": "https://tdn/a",
                        "text": "texto útil " * 8,
                        "body_len": 100,
                    }
                ),
                encoding="utf-8",
            )
            sync.write_json_atomic(
                store.manifest_path,
                {
                    "schema_version": 1,
                    "root_id": 1,
                    "pages": {"10": {"status": "active"}},
                },
            )
            output = Path(temp_dir) / "out"

            self.assertEqual(sync.export_offline(store, output), 1)
            exported = json.loads(
                (output / "tdn_pages.json").read_text(encoding="utf-8")
            )
            self.assertEqual(exported[0]["id"], 10)

    def test_snapshot_publishes_generation_v2_atomically(self) -> None:
        sync = load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            worker = sync.SnapshotSynchronizer(999, Path(temp_dir), 0)
            worker.collector.list_children = lambda _page_id: self.fail(
                "não deve listar filhos"
            )
            worker.fetch_page = lambda page_id: record(sync, page_id)

            result = worker.snapshot(0, None, 1, False, False)
            manifest = worker.store.load_manifest()

            self.assertEqual(result["pages_saved"], 1)
            self.assertEqual(manifest["schema_version"], 2)
            self.assertTrue(manifest["page_directory"].startswith("generations/"))
            self.assertTrue(
                (worker.store.pages_dir(manifest) / "999.json").is_file()
            )
            self.assertFalse((worker.store.root / "pages" / "999.json").exists())

    def test_refresh_failure_preserves_manifest_and_active_page_bytes(self) -> None:
        sync = load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            worker = sync.SnapshotSynchronizer(1, Path(temp_dir), 0)
            worker.collector.list_children = lambda _page_id: []
            worker.fetch_page = lambda page_id: record(
                sync,
                page_id,
                text="original " * 20,
            )
            worker.snapshot(0, None, 1, False, False)
            before_manifest = worker.store.manifest_path.read_bytes()
            before = worker.store.read_page(1)["text"]
            worker.discover_tree = lambda _depth, _limit: [1, 2]
            worker.fetch_version = lambda _page_id: {"number": 2, "when": "v2"}
            calls = {"count": 0}

            def fetch(page_id: int):
                calls["count"] += 1
                if calls["count"] == 2:
                    raise RuntimeError("rede caiu")
                return record(sync, page_id, text="novo " * 20, version=2)

            worker.fetch_page = fetch

            with self.assertRaisesRegex(RuntimeError, "rede caiu"):
                worker.refresh(1, None)

            self.assertEqual(
                worker.store.manifest_path.read_bytes(),
                before_manifest,
            )
            self.assertEqual(worker.store.read_page(1)["text"], before)

    def test_refresh_from_v1_migrates_to_v2_and_copies_unchanged_page(self) -> None:
        sync = load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            store = sync.SnapshotStore(Path(temp_dir), 1)
            pages = store.root / "pages"
            pages.mkdir(parents=True)
            page = record(sync, 1)
            sync.write_json_atomic(pages / "1.json", page)
            sync.write_json_atomic(
                store.manifest_path,
                {
                    "schema_version": 1,
                    "root_id": 1,
                    "created_at": "old",
                    "pages": {"1": sync.page_summary(page)},
                },
            )
            worker = sync.SnapshotSynchronizer(1, Path(temp_dir), 0)
            worker.discover_tree = lambda _depth, _limit: [1]
            worker.fetch_version = lambda _page_id: {
                "number": 1,
                "when": "v1",
            }
            worker.fetch_page = lambda _page_id: self.fail(
                "não deve baixar corpo inalterado"
            )

            result = worker.refresh(1, None)
            manifest = store.load_manifest()

            self.assertEqual(result["unchanged"], 1)
            self.assertEqual(manifest["schema_version"], 2)
            self.assertEqual(store.read_page(1, manifest)["text"], page["text"])

    def test_changed_page_below_minimum_becomes_filtered_not_stale(self) -> None:
        sync = load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            worker = sync.SnapshotSynchronizer(1, Path(temp_dir), 0)
            worker.collector.list_children = lambda _page_id: []
            worker.fetch_page = lambda page_id: record(sync, page_id)
            worker.snapshot(0, None, 1, False, False)
            worker.discover_tree = lambda _depth, _limit: [1]
            worker.fetch_version = lambda _page_id: {"number": 2, "when": "v2"}
            worker.fetch_page = lambda page_id: record(
                sync,
                page_id,
                text="stub",
                version=2,
            )

            result = worker.refresh(0, None)
            manifest = worker.store.load_manifest()

            self.assertEqual(result["filtered"], 1)
            self.assertEqual(manifest["pages"]["1"]["status"], "filtered")
            self.assertFalse(
                (worker.store.pages_dir(manifest) / "1.json").exists()
            )

    def test_lock_rejects_second_writer_and_is_not_removed_automatically(self) -> None:
        sync = load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "1"
            lock = sync.SnapshotLock(root)
            with lock, self.assertRaisesRegex(RuntimeError, "outra atualização"), sync.SnapshotLock(root):
                pass
            self.assertFalse(lock.path.exists())

            lock.path.parent.mkdir(parents=True, exist_ok=True)
            lock.path.write_text("orphan", encoding="utf-8")
            old_time = 1
            sync.os.utime(lock.path, (old_time, old_time))
            with self.assertRaisesRegex(RuntimeError, "lock órfão"), sync.SnapshotLock(root):
                pass
            self.assertTrue(lock.path.exists())

    def test_dry_run_is_bounded_and_never_publishes(self) -> None:
        sync = load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            worker = sync.SnapshotSynchronizer(1, Path(temp_dir), 1)
            worker.collector.list_children = lambda _page_id: []
            clock = [0.0]

            def monotonic() -> float:
                return clock[0]

            def sleep(seconds: float) -> None:
                clock[0] += seconds

            with (
                patch.object(sync.time, "monotonic", monotonic),
                patch.object(sync.time, "sleep", sleep),
            ):
                result = worker.snapshot(
                    0,
                    None,
                    1,
                    True,
                    False,
                    max_duration_seconds=0.1,
                )

            self.assertFalse(result["complete"])
            self.assertEqual(result["stop_reason"], "max-duration")
            self.assertIsNone(worker.store.load_manifest())

    def test_resume_uses_same_staging_generation(self) -> None:
        sync = load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            store = sync.SnapshotStore(Path(temp_dir), 1)
            run_id = "resume-test"
            (store.staging_dir(run_id) / "pages").mkdir(parents=True)
            store.write_state(
                {
                    "mode": "snapshot",
                    "run_id": run_id,
                    "root_id": 1,
                    "max_depth": 0,
                    "delay_seconds": 0,
                    "pending_ids": [1],
                    "completed_ids": [],
                    "pages": {},
                    "started_at": "2026-01-01T00:00:00+00:00",
                }
            )
            worker = sync.SnapshotSynchronizer(1, Path(temp_dir), 0)
            worker.fetch_page = lambda page_id: record(sync, page_id)

            worker.snapshot(0, None, 1, False, True)
            manifest = store.load_manifest()

            self.assertEqual(manifest["generation_id"], run_id)
            self.assertIsNone(store.load_state())

    def test_existing_partial_state_blocks_new_snapshot_without_resume(self) -> None:
        sync = load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            worker = sync.SnapshotSynchronizer(1, Path(temp_dir), 0)
            worker.store.write_state(
                {
                    "mode": "snapshot",
                    "run_id": "partial",
                    "root_id": 1,
                    "pending_ids": [1],
                }
            )
            worker.discover_tree = lambda _depth, _limit: [1]

            with self.assertRaisesRegex(RuntimeError, "execução parcial"):
                worker.snapshot(0, None, 1, False, False)

    def test_existing_partial_state_blocks_refresh(self) -> None:
        sync = load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            worker = sync.SnapshotSynchronizer(1, Path(temp_dir), 0)
            worker.store.write_state(
                {
                    "mode": "snapshot",
                    "run_id": "partial",
                    "root_id": 1,
                }
            )

            with self.assertRaisesRegex(RuntimeError, "execução parcial"):
                worker.refresh(0, None)

    def test_refresh_deadline_rolls_back_staging_and_preserves_active_snapshot(self) -> None:
        sync = load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            worker = sync.SnapshotSynchronizer(1, Path(temp_dir), 0)
            worker.collector.list_children = lambda _page_id: []
            worker.fetch_page = lambda page_id: record(sync, page_id)
            worker.snapshot(0, None, 1, False, False)
            before_manifest = worker.store.manifest_path.read_bytes()
            before_page = worker.store.read_page(1)["text"]
            worker.discover_tree = lambda _depth, _limit: [1, 2]
            worker.fetch_version = lambda _page_id: {"number": 2, "when": "v2"}
            worker.fetch_page = lambda page_id: record(sync, page_id, version=2)
            clock = [0.0]

            def monotonic() -> float:
                return clock[0]

            def sleep(seconds: float) -> None:
                clock[0] += max(seconds, 0.06)

            with (
                patch.object(sync.time, "monotonic", monotonic),
                patch.object(sync.time, "sleep", sleep),
                self.assertRaisesRegex(sync.SnapshotDurationReached, "prazo máximo"),
            ):
                worker.refresh(1, None, max_duration_seconds=0.1)

            self.assertEqual(worker.store.manifest_path.read_bytes(), before_manifest)
            self.assertEqual(worker.store.read_page(1)["text"], before_page)
            staging = worker.store.root / ".staging"
            leftovers = list(staging.iterdir()) if staging.is_dir() else []
            self.assertEqual(leftovers, [])


if __name__ == "__main__":
    unittest.main()
