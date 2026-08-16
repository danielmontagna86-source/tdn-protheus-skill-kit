"""Gera o ZIP portátil do Skill Kit a partir de uma allowlist explícita."""
from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ARCHIVE_ROOT = "tdn-protheus-skill-kit"
ROOT_FILES = (
    "README.md", "CHANGELOG.md", "LICENSE", "NOTICE.md", "SECURITY.md",
    "SUPPORT.md", "CONTRIBUTING.md", "VERSION", "install.py", "requirements.txt",
)
ROOT_DIRS = ("coletando-documentacao-tdn-protheus", "docs")
EXCLUDED_PARTS = {".venv", "__pycache__", "tdn-cache", "build", "dist"}
EXCLUDED_PREFIXES = ("saida-",)


def include_file(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    return (
        not any(part in EXCLUDED_PARTS or part.startswith(EXCLUDED_PREFIXES) or part.endswith(".egg-info") for part in relative.parts)
        and path.suffix not in {".pyc", ".pyo", ".tmp", ".jsonl"}
        and path.name not in {"tdn_pages.json", "tdn_pages.jsonl", "tdn_errors.jsonl"}
    )


def iter_files():
    for name in ROOT_FILES:
        path = ROOT / name
        if path.is_file():
            yield path
    for dirname in ROOT_DIRS:
        directory = ROOT / dirname
        if not directory.is_dir():
            continue
        for path in directory.rglob("*"):
            if path.is_file() and include_file(path):
                yield path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT.parent / "tdn-protheus-skill-kit.zip")
    args = parser.parse_args()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(set(iter_files())):
            archive.write(path, Path(ARCHIVE_ROOT) / path.relative_to(ROOT))
    print(f"OK: pacote criado em {output}")


if __name__ == "__main__":
    main()
