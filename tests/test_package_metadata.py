from __future__ import annotations

import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


class PackageMetadataTests(unittest.TestCase):
    def test_project_declares_public_mcp_command_and_python_support(self) -> None:
        with (ROOT / "pyproject.toml").open("rb") as handle:
            project = tomllib.load(handle)["project"]

        self.assertEqual(project["name"], "tdn-protheus-mcp")
        self.assertEqual(project["requires-python"], ">=3.11")
        self.assertEqual(project["scripts"]["tdn-protheus-mcp"], "tdn_protheus_mcp.cli:main")
        self.assertIn("Apache-2.0", project["license"])


if __name__ == "__main__":
    unittest.main()
