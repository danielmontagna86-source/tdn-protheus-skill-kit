from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).parents[1]
SKILL_DIR = ROOT / "coletando-documentacao-tdn-protheus"
SKILL = SKILL_DIR / "SKILL.md"
INSTALLER = ROOT / "install.py"
VALIDATOR = SKILL_DIR / "scripts" / "validate_skill.py"
RELEASE_WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"


def run_command(command: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )


class ValidateSkillTests(unittest.TestCase):
    def test_repository_contains_no_embedded_mcp_implementation(self) -> None:
        self.assertFalse((ROOT / "tdn_protheus_mcp").exists())
        self.assertFalse((ROOT / "tdn-protheus-mcp.config.example.json").exists())
        self.assertFalse((ROOT / "docs" / "mcp-protocol-contract.md").exists())

    def test_portable_skill_passes_contract_validation(self) -> None:
        result = run_command([sys.executable, str(VALIDATOR), str(SKILL_DIR)])

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("OK", result.stdout)

    def test_skill_declares_hermes_agent_output_contract(self) -> None:
        text = SKILL.read_text(encoding="utf-8")
        fields = (
            "Hermes Agent",
            "source_url",
            "chunk_index",
            "target_audience",
            "content",
        )
        for field in fields:
            self.assertIn(field, text)

    def test_processor_generates_the_jsonl_contract(self) -> None:
        expected_fields = {
            "id",
            "source_url",
            "title",
            "chunk_index",
            "total_chunks",
            "modules",
            "tables",
            "parameters",
            "routines",
            "entry_points",
            "target_audience",
            "content",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            source = temp / "tdn_pages.json"
            output = temp / "chunks.jsonl"
            source.write_text(
                json.dumps(
                    [
                        {
                            "id": 42,
                            "url": "https://tdn.totvs.com/example",
                            "title": "ADVPL e SIGAFAT",
                            "text": (
                                "Use MATA410 com a tabela SC5 e o parametro "
                                "MV_TESTE."
                            ),
                        }
                    ]
                ),
                encoding="utf-8",
            )

            result = run_command(
                [
                    sys.executable,
                    str(SKILL_DIR / "scripts" / "process_tdn.py"),
                    str(source),
                    str(output),
                ]
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            records = [
                json.loads(line)
                for line in output.read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(len(records), 1)
            self.assertEqual(set(records[0]), expected_fields)
            self.assertEqual(
                records[0]["source_url"],
                "https://tdn.totvs.com/example",
            )

    def test_scripts_expose_help_without_network(self) -> None:
        scripts = (
            "collect_tdn.py",
            "locate_tdn_pages.py",
            "process_tdn.py",
            "sync_tdn_snapshot.py",
        )
        for script in scripts:
            result = run_command(
                [sys.executable, str(SKILL_DIR / "scripts" / script), "--help"]
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("usage:", result.stdout.lower())

    def test_installer_dry_run_reports_target_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "skills"
            result = run_command(
                [
                    sys.executable,
                    str(INSTALLER),
                    "--platform",
                    "codex",
                    "--target",
                    str(target),
                    "--dry-run",
                ]
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertFalse(target.exists())

    def test_installer_refuses_to_replace_existing_skill_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "skills"
            existing = target / "coletando-documentacao-tdn-protheus"
            existing.mkdir(parents=True)
            marker = existing / "user-file.txt"
            marker.write_text("preserve me", encoding="utf-8")

            result = run_command(
                [
                    sys.executable,
                    str(INSTALLER),
                    "--platform",
                    "codex",
                    "--target",
                    str(target),
                    "--skip-deps",
                ]
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(marker.is_file())

    def test_installer_replaces_existing_skill_only_with_force(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "skills"
            existing = target / "coletando-documentacao-tdn-protheus"
            existing.mkdir(parents=True)
            (existing / "stale.txt").write_text("old", encoding="utf-8")

            result = run_command(
                [
                    sys.executable,
                    str(INSTALLER),
                    "--platform",
                    "codex",
                    "--target",
                    str(target),
                    "--skip-deps",
                    "--force",
                ]
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertTrue((existing / "SKILL.md").is_file())
            self.assertFalse((existing / "stale.txt").exists())

    def test_release_workflow_does_not_build_a_python_mcp_package(self) -> None:
        workflow = RELEASE_WORKFLOW.read_text(encoding="utf-8")

        self.assertNotIn("python -m build", workflow)
        self.assertNotIn("twine", workflow)
        self.assertIn("tdn-protheus-skill-kit-${GITHUB_REF_NAME}.zip", workflow)

    def test_package_is_allowlisted_and_contains_no_mcp_or_local_data(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package_root = Path(temp_dir) / "kit"
            shutil.copytree(ROOT, package_root)
            forbidden_files = (
                "tdn_protheus_mcp/server.py",
                "tdn-cache/page.json",
                "saida-local/tdn_pages.json",
                "sample.jsonl",
                ".venv/secret",
            )
            for relative in forbidden_files:
                path = package_root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("not for distribution", encoding="utf-8")

            output = package_root / "dist" / "release.zip"
            result = run_command(
                [
                    sys.executable,
                    str(package_root / "package.py"),
                    "--output",
                    str(output),
                ]
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

            with zipfile.ZipFile(output) as archive:
                names = archive.namelist()

            self.assertTrue(
                any(
                    name.endswith(
                        "/coletando-documentacao-tdn-protheus/SKILL.md"
                    )
                    for name in names
                )
            )
            forbidden_parts = (
                "tdn_protheus_mcp",
                "/tdn-cache/",
                "/saida-local/",
                "/.venv/",
            )
            self.assertFalse(
                any(
                    any(part in name for part in forbidden_parts)
                    or name.endswith(".jsonl")
                    for name in names
                ),
                names,
            )


if __name__ == "__main__":
    unittest.main()
