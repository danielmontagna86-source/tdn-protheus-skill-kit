from __future__ import annotations

import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "install.py"


def load_module():
    spec = importlib.util.spec_from_file_location("skill_installer", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class InstallerTransactionTests(unittest.TestCase):
    def test_prepare_failure_leaves_existing_installation_untouched(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            skills = Path(temp_dir) / "skills"
            destination = skills / module.SKILL_NAME
            destination.mkdir(parents=True)
            marker = destination / "keep.txt"
            marker.write_text("old", encoding="utf-8")

            def failing_runner(*_args, **_kwargs):
                raise subprocess.CalledProcessError(1, "test")

            with self.assertRaises(subprocess.CalledProcessError):
                module.prepare_staging(
                    skills,
                    skip_deps=True,
                    runner=failing_runner,
                )

            self.assertEqual(marker.read_text(encoding="utf-8"), "old")
            leftovers = [
                path
                for path in skills.iterdir()
                if path.name.startswith(f".{module.SKILL_NAME}.staging-")
            ]
            self.assertEqual(leftovers, [])

    def test_publish_force_swaps_only_after_staging_is_complete(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            skills = Path(temp_dir)
            destination = skills / module.SKILL_NAME
            destination.mkdir()
            (destination / "old.txt").write_text("old", encoding="utf-8")
            staging = skills / ".stage"
            staging.mkdir()
            (staging / "new.txt").write_text("new", encoding="utf-8")

            module.publish_staging(staging, destination, force=True)

            self.assertFalse((destination / "old.txt").exists())
            self.assertEqual(
                (destination / "new.txt").read_text(encoding="utf-8"),
                "new",
            )


if __name__ == "__main__":
    unittest.main()
