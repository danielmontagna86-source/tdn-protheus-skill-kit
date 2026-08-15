"""Instala a skill TDN Protheus em Claude Code, Codex, Antigravity ou loader OpenRouter."""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path


SKILL_NAME = "coletando-documentacao-tdn-protheus"
SOURCE_ROOT = Path(__file__).resolve().parent
SOURCE_SKILL = SOURCE_ROOT / SKILL_NAME


def default_target(platform: str, scope: str) -> Path:
    home = Path.home()
    project = Path.cwd()
    mappings = {
        "claude": (project / ".claude" / "skills", home / ".claude" / "skills"),
        "codex": (project / ".codex" / "skills", home / ".codex" / "skills"),
        "antigravity": (project / ".agents" / "skills", home / ".gemini" / "config" / "skills"),
        # O loader oficial de exemplo do OpenRouter usa a convenção Claude.
        "openrouter": (project / ".claude" / "skills", home / ".claude" / "skills"),
    }
    return mappings[platform][0 if scope == "project" else 1]


def python_in(venv_dir: Path) -> Path:
    return venv_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", required=True, choices=("claude", "codex", "antigravity", "openrouter"))
    parser.add_argument("--scope", default="project", choices=("project", "user"))
    parser.add_argument("--target", type=Path, help="Diretório de skills; substitui o destino padrão")
    parser.add_argument("--force", action="store_true", help="Substitui uma skill existente no destino")
    parser.add_argument("--skip-deps", action="store_true", help="Não criar .venv nem instalar requirements")
    parser.add_argument("--dry-run", action="store_true", help="Exibe o plano sem gravar arquivos")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not SOURCE_SKILL.is_dir():
        raise SystemExit(f"Skill-fonte ausente: {SOURCE_SKILL}")
    skills_dir = (args.target or default_target(args.platform, args.scope)).expanduser().resolve()
    destination = skills_dir / SKILL_NAME
    occupied = destination.exists() and (not destination.is_dir() or any(destination.iterdir()))
    if occupied and not args.force:
        raise SystemExit(f"Destino já contém uma skill: {destination}. Revise o conteúdo ou use --force para substituí-la.")
    if args.dry_run:
        print(f"DRY-RUN: copiaria {SOURCE_SKILL} para {destination}")
        if not args.skip_deps:
            print(f"DRY-RUN: criaria ambiente Python e instalaria requirements em {destination / '.venv'}")
        return
    skills_dir.mkdir(parents=True, exist_ok=True)
    if occupied:
        if destination.is_dir():
            shutil.rmtree(destination)
        else:
            destination.unlink()
    shutil.copytree(SOURCE_SKILL, destination, dirs_exist_ok=True)
    validator = destination / "scripts" / "validate_skill.py"
    result = subprocess.run([sys.executable, str(validator), str(destination)], check=False)
    if result.returncode:
        raise SystemExit("Instalação abortada: validação estrutural falhou")
    if not args.skip_deps:
        venv_dir = destination / ".venv"
        venv.EnvBuilder(with_pip=True).create(venv_dir)
        subprocess.run(
            [str(python_in(venv_dir)), "-m", "pip", "install", "--quiet", "--disable-pip-version-check", "--upgrade", "pip"],
            check=True,
        )
        subprocess.run(
            [str(python_in(venv_dir)), "-m", "pip", "install", "--quiet", "--disable-pip-version-check", "-r", str(destination / "requirements.txt")],
            check=True,
        )
    if args.platform == "openrouter":
        print("NOTA: configure o loader do seu agente OpenRouter para descobrir este diretório.")
    print(f"OK: skill instalada em {destination}")


if __name__ == "__main__":
    main()
