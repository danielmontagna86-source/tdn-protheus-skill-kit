from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).parents[1]
SKILL = ROOT / "coletando-documentacao-tdn-protheus" / "SKILL.md"
INSTALLER = ROOT / "install.py"
SKILL_DIR = ROOT / "coletando-documentacao-tdn-protheus"
VALIDATOR = SKILL_DIR / "scripts" / "validate_skill.py"
RELEASE_WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"


class ValidateSkillTests(unittest.TestCase):
    def test_portable_skill_passes_contract_validation(self) -> None:
        result = subprocess.run(
        [sys.executable, str(VALIDATOR), str(SKILL_DIR)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("OK", result.stdout)

    def test_skill_declares_hermes_agent_output_contract(self) -> None:
        text = SKILL.read_text(encoding="utf-8")
        for field in ("Hermes Agent", "source_url", "chunk_index", "target_audience", "content"):
            self.assertIn(field, text)

    def test_processor_generates_the_hermes_jsonl_contract(self) -> None:
        expected_fields = {
            "id", "source_url", "title", "chunk_index", "total_chunks",
            "modules", "tables", "parameters", "routines", "entry_points",
            "target_audience", "content",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            source = temp / "tdn_pages.json"
            output = temp / "hermes_chunks.jsonl"
            source.write_text(json.dumps([{
                "id": 42,
                "url": "https://tdn.totvs.com/example",
                "title": "ADVPL e SIGAFAT",
                "text": "Use MATA410 com a tabela SC5 e o parametro MV_TESTE.",
            }]), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SKILL_DIR / "scripts" / "process_tdn.py"), str(source), str(output)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            records = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(records), 1)
            self.assertEqual(set(records[0]), expected_fields)
            self.assertEqual(records[0]["source_url"], "https://tdn.totvs.com/example")
            self.assertTrue(records[0]["content"])

    def test_scripts_expose_help_without_network(self) -> None:
        for script in ("collect_tdn.py", "process_tdn.py", "sync_tdn_snapshot.py"):
            result = subprocess.run(
                [sys.executable, str(SKILL_DIR / "scripts" / script), "--help"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("usage:", result.stdout.lower())

    def test_installer_dry_run_reports_target_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "skills"
            result = subprocess.run(
                [sys.executable, str(INSTALLER), "--platform", "codex", "--target", str(target), "--dry-run"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("DRY-RUN", result.stdout)
            self.assertFalse(target.exists())

    def test_installer_refuses_to_replace_existing_skill_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "skills"
            existing = target / "coletando-documentacao-tdn-protheus"
            existing.mkdir(parents=True)
            marker = existing / "user-file.txt"
            marker.write_text("preserve me", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(INSTALLER), "--platform", "codex", "--target", str(target), "--skip-deps"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("--force", result.stderr + result.stdout)
            self.assertTrue(marker.is_file())

    def test_installer_replaces_existing_skill_only_with_force(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "skills"
            existing = target / "coletando-documentacao-tdn-protheus"
            existing.mkdir(parents=True)
            (existing / "stale.txt").write_text("old", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(INSTALLER), "--platform", "codex", "--target", str(target), "--skip-deps", "--force"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertTrue((existing / "SKILL.md").is_file())
            self.assertFalse((existing / "stale.txt").exists())

    def test_installer_copies_and_validates_skill_without_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "skills"
            result = subprocess.run(
                [sys.executable, str(INSTALLER), "--platform", "codex", "--target", str(target), "--skip-deps"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            installed = target / "coletando-documentacao-tdn-protheus"
            self.assertTrue((installed / "SKILL.md").is_file())
            snapshot_help = subprocess.run(
                [sys.executable, str(installed / "scripts" / "sync_tdn_snapshot.py"), "--help"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(snapshot_help.returncode, 0, snapshot_help.stderr + snapshot_help.stdout)


class PackageReleaseTests(unittest.TestCase):
    def test_release_metadata_has_one_consistent_version(self) -> None:
        expected = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        init = (ROOT / "tdn_protheus_mcp" / "__init__.py").read_text(encoding="utf-8")

        self.assertEqual(project["project"]["version"], expected)
        self.assertIn(f'__version__ = "{expected}"', init)

    def test_release_workflow_publishes_only_portable_skill_assets(self) -> None:
        workflow = RELEASE_WORKFLOW.read_text(encoding="utf-8")

        self.assertNotIn("python -m build", workflow)
        self.assertNotIn("python -m twine", workflow)
        self.assertNotIn("cyclonedx", workflow)
        self.assertIn('gh release create "${GITHUB_REF_NAME}" "dist/tdn-protheus-skill-kit-${GITHUB_REF_NAME}.zip" dist/SHA256SUMS.txt', workflow)

    def test_package_excludes_repository_metadata_and_local_data(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package_root = Path(temp_dir) / "kit"
            shutil.copytree(ROOT, package_root)
            for relative in (".git/config", ".github/workflows/ci.yml", ".venv/secret", "tdn-cache/page.json", "saida-local/tdn_pages.json", "sample.jsonl"):
                path = package_root / relative
                if path.parent.is_file():
                    path.parent.unlink()
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("not for distribution", encoding="utf-8")
            output = package_root / "dist" / "release.zip"
            result = subprocess.run(
                [sys.executable, str(package_root / "package.py"), "--output", str(output)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            with zipfile.ZipFile(output) as archive:
                names = archive.namelist()
            forbidden = ("/.git/", "/.github/", "/.venv/", "/tdn-cache/", "/saida-local/", "/tdn_protheus_mcp.egg-info/", ".jsonl")
            self.assertFalse(any(item in name or name.endswith(item) for name in names for item in forbidden), names)
