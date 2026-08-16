from __future__ import annotations

import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import package as packager


class PackageTests(unittest.TestCase):
    def test_include_file_rejects_local_runtime_artifacts(self) -> None:
        self.assertTrue(packager.include_file(packager.ROOT / "docs" / "install.md"))
        self.assertFalse(packager.include_file(packager.ROOT / "tdn-cache" / "page.json"))
        self.assertFalse(packager.include_file(packager.ROOT / "saida-local" / "page.json"))
        self.assertFalse(packager.include_file(packager.ROOT / "docs" / "chunks.jsonl"))
        self.assertFalse(packager.include_file(packager.ROOT / ".venv" / "secret.py"))

    def test_iter_files_is_allowlisted_and_excludes_mcp_payload(self) -> None:
        files = list(packager.iter_files())
        relatives = {path.relative_to(packager.ROOT).as_posix() for path in files}
        self.assertIn("README.md", relatives)
        self.assertIn("coletando-documentacao-tdn-protheus/SKILL.md", relatives)
        self.assertFalse(any(path.startswith("tdn_protheus_mcp/") for path in relatives))
        self.assertFalse(any(path.endswith(".jsonl") for path in relatives))

    def test_main_creates_a_portable_zip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "skill-kit.zip"
            with patch.object(sys, "argv", ["package.py", "--output", str(output)]):
                packager.main()

            self.assertTrue(output.is_file())
            with zipfile.ZipFile(output) as archive:
                names = set(archive.namelist())
            self.assertIn(
                "tdn-protheus-skill-kit/coletando-documentacao-tdn-protheus/SKILL.md",
                names,
            )
            self.assertFalse(any("tdn_protheus_mcp" in name for name in names))


if __name__ == "__main__":
    unittest.main()
