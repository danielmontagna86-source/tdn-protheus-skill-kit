from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from tdn_protheus_mcp.config import ConfigError, load_config  # noqa: E402


class ConfigTests(unittest.TestCase):
    def test_load_config_defaults_to_offline_and_limits_results(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "mcp.json"
            cache_root = Path(temp_dir) / "cache"
            cache_root.mkdir()
            config_path.write_text(json.dumps({"cache_root": str(cache_root), "allowed_root_ids": ["235312129"]}), encoding="utf-8")

            config = load_config(config_path)

            self.assertTrue(config.offline)
            self.assertEqual(config.allowed_root_ids, frozenset({"235312129"}))
            self.assertEqual(config.max_results, 20)
            self.assertEqual(config.max_chars, 24000)

    def test_load_config_rejects_unknown_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "mcp.json"
            config_path.write_text(json.dumps({"cache_root": temp_dir, "allowed_root_ids": ["1"], "unsafe": True}), encoding="utf-8")

            with self.assertRaisesRegex(ConfigError, "CONFIG_UNKNOWN_FIELD"):
                load_config(config_path)


if __name__ == "__main__":
    unittest.main()
