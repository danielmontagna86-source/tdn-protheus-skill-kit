"""Valida a estrutura portátil da skill sem acessar a rede."""
from __future__ import annotations

import re
import sys
from pathlib import Path


def fail(message: str) -> None:
    raise SystemExit(f"ERRO: {message}")


def main() -> None:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    skill = root / "SKILL.md"
    if not skill.is_file():
        fail(f"SKILL.md não encontrado: {skill}")
    text = skill.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not match:
        fail("frontmatter YAML ausente")
    keys = [line.split(":", 1)[0] for line in match.group(1).splitlines() if ":" in line]
    if keys != ["name", "description"]:
        fail("o frontmatter deve conter apenas name e description, nesta ordem")
    required = (
        "https://tdn.totvs.com/rest/api", "body.storage", "child/page?limit=50&start=N",
        "237387586", "235312129", "811253122", "811253174", "tdn_pages.json", "tdn_chunks.jsonl",
        "Hermes Agent", "source_url", "chunk_index", "target_audience", "content",
    )
    missing = [item for item in required if item not in text]
    if missing:
        fail("marcadores ausentes: " + ", ".join(missing))
    for script in ("collect_tdn.py", "process_tdn.py", "sync_tdn_snapshot.py"):
        if not (root / "scripts" / script).is_file():
            fail(f"script ausente: {script}")
    if not (root / "requirements.txt").is_file():
        fail("requirements.txt ausente")
    print("OK: skill portátil válida; frontmatter, workflow e scripts presentes.")


if __name__ == "__main__":
    main()
