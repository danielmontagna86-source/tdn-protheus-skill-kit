"""Gera ZIP distribuível do kit, excluindo cache local e ambientes Python."""
from __future__ import annotations

import argparse
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
EXCLUDED_PARTS = {".git", ".github", ".venv", "tdn-cache", "__pycache__", "build", "dist"}
EXCLUDED_PREFIXES = ("saida-",)
EXCLUDED_FILENAMES = {"tdn_pages.json", "tdn_pages.jsonl", "tdn_errors.jsonl"}


def should_include(path: Path, output: Path) -> bool:
    relative = path.relative_to(ROOT)
    return (
        path.resolve() != output.resolve()
        and not any(part in EXCLUDED_PARTS or part.startswith(EXCLUDED_PREFIXES) or part.endswith(".egg-info") for part in relative.parts)
        and path.name not in EXCLUDED_FILENAMES
        and path.suffix not in {".pyc", ".pyo", ".tmp", ".jsonl"}
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT.parent / f"{ROOT.name}.zip")
    args = parser.parse_args()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in ROOT.rglob("*"):
            if path.is_file() and should_include(path, output):
                archive.write(path, ROOT.name / path.relative_to(ROOT))
    print(f"OK: pacote criado em {output}")


if __name__ == "__main__":
    main()
