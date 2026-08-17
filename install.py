"""Instala a skill TDN Protheus de forma transacional em harnesses suportados."""
from __future__ import annotations

import argparse
import os
import shutil
import stat
import subprocess
import sys
import uuid
import venv
from collections.abc import Callable
from pathlib import Path

SKILL_NAME = "coletando-documentacao-tdn-protheus"
SOURCE_ROOT = Path(__file__).resolve().parent
SOURCE_SKILL = SOURCE_ROOT / SKILL_NAME
Runner = Callable[..., subprocess.CompletedProcess]


def remove_tree(path: Path) -> None:
    def retry_writable(operation: Callable[..., object], failed_path: str, _exc) -> None:
        os.chmod(failed_path, stat.S_IWRITE)
        operation(failed_path)

    shutil.rmtree(path, onerror=retry_writable)


def default_target(platform: str, scope: str) -> Path:
    home = Path.home()
    project = Path.cwd()
    mappings = {
        "claude": (project / ".claude" / "skills", home / ".claude" / "skills"),
        "codex": (project / ".codex" / "skills", home / ".codex" / "skills"),
        "antigravity": (
            project / ".agents" / "skills",
            home / ".gemini" / "config" / "skills",
        ),
        "openrouter": (project / ".claude" / "skills", home / ".claude" / "skills"),
    }
    return mappings[platform][0 if scope == "project" else 1]


def python_in(venv_dir: Path) -> Path:
    return venv_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def validate_skill(path: Path, runner: Runner = subprocess.run) -> None:
    command = [
        sys.executable,
        str(path / "scripts" / "validate_skill.py"),
        str(path),
    ]
    result = runner(command, check=False)
    if result.returncode:
        raise RuntimeError("validação estrutural da skill falhou")


def prepare_staging(
    skills_dir: Path,
    *,
    skip_deps: bool,
    runner: Runner = subprocess.run,
) -> Path:
    staging = skills_dir / f".{SKILL_NAME}.staging-{uuid.uuid4().hex[:10]}"
    shutil.copytree(SOURCE_SKILL, staging)
    try:
        validate_skill(staging, runner)
        if not skip_deps:
            venv_dir = staging / ".venv"
            venv.EnvBuilder(with_pip=True).create(venv_dir)
            python = str(python_in(venv_dir))
            common = [
                python,
                "-m",
                "pip",
                "install",
                "--quiet",
                "--disable-pip-version-check",
            ]
            runner([*common, "--upgrade", "pip"], check=True)
            runner(
                [*common, "-r", str(staging / "requirements.txt")],
                check=True,
            )
            validate_skill(staging, runner)
        return staging
    except Exception:
        remove_tree(staging)
        raise


def publish_staging(staging: Path, destination: Path, *, force: bool) -> None:
    occupied = destination.exists() and (
        not destination.is_dir() or any(destination.iterdir())
    )
    if occupied and not force:
        raise RuntimeError(
            f"Destino já contém uma skill: {destination}. "
            "Revise o conteúdo ou use --force para substituí-la."
        )
    backup: Path | None = None
    try:
        if occupied:
            backup = destination.parent / (
                f".{SKILL_NAME}.backup-{uuid.uuid4().hex[:10]}"
            )
            os.replace(destination, backup)
        os.replace(staging, destination)
    except Exception:
        if backup is not None and backup.exists() and not destination.exists():
            os.replace(backup, destination)
        raise
    else:
        if backup is not None:
            remove_tree(backup)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--platform",
        required=True,
        choices=("claude", "codex", "antigravity", "openrouter"),
    )
    parser.add_argument("--scope", default="project", choices=("project", "user"))
    parser.add_argument("--target", type=Path)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--skip-deps", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not SOURCE_SKILL.is_dir():
        raise SystemExit(f"Skill-fonte ausente: {SOURCE_SKILL}")
    skills_dir = (
        args.target or default_target(args.platform, args.scope)
    ).expanduser().resolve()
    destination = skills_dir / SKILL_NAME
    occupied = destination.exists() and (
        not destination.is_dir() or any(destination.iterdir())
    )
    if occupied and not args.force:
        raise SystemExit(
            f"Destino já contém uma skill: {destination}. "
            "Revise o conteúdo ou use --force para substituí-la."
        )
    if args.dry_run:
        print(
            f"DRY-RUN: validaria e prepararia {SOURCE_SKILL} "
            f"antes de publicar em {destination}"
        )
        return
    skills_dir.mkdir(parents=True, exist_ok=True)
    try:
        staging = prepare_staging(skills_dir, skip_deps=args.skip_deps)
        publish_staging(staging, destination, force=args.force)
    except (RuntimeError, subprocess.CalledProcessError, OSError) as error:
        raise SystemExit(
            "Instalação abortada sem substituir a instalação anterior: "
            f"{error}"
        ) from error
    if args.platform == "openrouter":
        print("NOTA: configure o loader OpenRouter para descobrir este diretório.")
    print(f"OK: skill instalada em {destination}")


if __name__ == "__main__":
    main()
