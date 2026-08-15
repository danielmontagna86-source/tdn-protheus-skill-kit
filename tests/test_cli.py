from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


class CliTests(unittest.TestCase):
    def test_doctor_reports_a_valid_offline_configuration_without_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_root = Path(temp_dir) / "cache"
            cache_root.mkdir()
            config_path = Path(temp_dir) / "mcp.json"
            config_path.write_text(json.dumps({"cache_root": str(cache_root), "allowed_root_ids": ["235312129"]}), encoding="utf-8")

            result = subprocess.run(
                [sys.executable, "-m", "tdn_protheus_mcp", "doctor", "--config", str(config_path), "--json"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertTrue(payload["config"]["offline"])
            self.assertEqual(payload["diagnostics"][0]["code"], "SNAPSHOT_NOT_FOUND")

    def test_index_search_and_status_emit_structured_local_results(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_root = Path(temp_dir) / "cache"
            pages_dir = cache_root / "1" / "pages"
            pages_dir.mkdir(parents=True)
            (pages_dir / "10.json").write_text(json.dumps({"id": 10, "title": "FWRest", "url": "https://tdn.totvs.com/10", "text": "FWRest usa HTTP.", "fetched_at": "2026-08-15"}), encoding="utf-8")
            (cache_root / "1" / "manifest.json").write_text(json.dumps({"root_id": 1, "pages": {"10": {"status": "active"}}}), encoding="utf-8")
            config_path = Path(temp_dir) / "mcp.json"
            config_path.write_text(json.dumps({"cache_root": str(cache_root), "allowed_root_ids": ["1"]}), encoding="utf-8")

            index = subprocess.run([sys.executable, "-m", "tdn_protheus_mcp", "index", "--config", str(config_path), "--root-id", "1", "--json"], cwd=ROOT, capture_output=True, text=True, check=False)
            search = subprocess.run([sys.executable, "-m", "tdn_protheus_mcp", "search", "--config", str(config_path), "--root-id", "1", "--query", "FWRest", "--json"], cwd=ROOT, capture_output=True, text=True, check=False)
            status = subprocess.run([sys.executable, "-m", "tdn_protheus_mcp", "status", "--config", str(config_path), "--root-id", "1", "--json"], cwd=ROOT, capture_output=True, text=True, check=False)

            self.assertEqual(index.returncode, 0, index.stderr)
            self.assertEqual(json.loads(index.stdout)["chunks_indexed"], 1)
            self.assertEqual(search.returncode, 0, search.stderr)
            self.assertEqual(json.loads(search.stdout)["results"][0]["source_url"], "https://tdn.totvs.com/10")
            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertEqual(json.loads(status.stdout)["active_pages"], 1)


if __name__ == "__main__":
    unittest.main()
