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


if __name__ == "__main__":
    unittest.main()
