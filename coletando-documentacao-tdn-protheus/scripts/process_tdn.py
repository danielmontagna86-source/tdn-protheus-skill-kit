"""Transforma tdn_pages.json em chunks JSONL com metadados Protheus."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200
MODULE_PATTERNS = {
    "ADVPL": r"\b(ADVPL|TLPP|MSEXECAUTO|EXEC_AUTO|USER\s*FUNCTION)\b",
    "SIGAFAT": r"\b(SIGAFAT|FATURAMENTO|MATA410|MATA460|MATA461|SC5|SC6|SF2|SD2)\b",
    "SIGACOM": r"\b(SIGACOM|COMPRAS|MATA110|MATA120|MATA103|SC1|SC7|SF1|SD1)\b",
    "SIGAEST": r"\b(SIGAEST|ESTOQUE|MATA240|MATA330|SB1|SB2|SD3)\b",
    "SIGAFIN": r"\b(SIGAFIN|FINANCEIRO|FINA040|FINA050|SE1|SE2|SE5)\b",
    "SIGACTB": r"\b(SIGACTB|CONTABILIDADE|CTBA102|CTBA105|CT1|CT2)\b",
    "SIGAFIS": r"\b(SIGAFIS|FISCAL|SPED|FISA001|FISA170|SF3|SFT|SF4)\b",
    "SIGAATF": r"\b(SIGAATF|ATIVO\s*FIXO|ATFA012|ATFA050|SN1|SN3)\b",
    "SIGAGCT": r"\b(SIGAGCT|CONTRATOS|CNTA300|CNTA120|CN9|CNC|CND)\b",
}
TABLE = re.compile(r"\b(?:S[A-Z0-9]{2}|F0[A-Z0-9]|CN[A-Z0-9]|CT[A-Z0-9]|SN[1-5])\b", re.I)
PARAMETER = re.compile(r"\bMV_[A-Z0-9_]{3,}\b", re.I)
ROUTINE = re.compile(r"\b(?=[A-Z0-9]{6,20}\b)(?=[A-Z0-9]*\d)[A-Z][A-Z0-9]+\b", re.I)
EXPLICIT_ENTRY = re.compile(r"\b(?:ADV[0-9]+_PE_[A-Z0-9_]+|[A-Z0-9]{3,}_PE(?:_[A-Z0-9_]+)?)\b", re.I)
PROGRAM_PREFIXES = ("MATA", "FINA", "CTBA", "FISA", "ATFA", "CNTA", "SPED")


def split_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Divide texto por limites naturais com overlap determinístico e sem dependência externa."""
    normalized = text.strip()
    if not normalized:
        return []
    if chunk_size < 1 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("chunk_size/overlap inválidos")
    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        hard_end = min(len(normalized), start + chunk_size)
        end = hard_end
        if hard_end < len(normalized):
            lower = start + chunk_size // 2
            candidates = (
                normalized.rfind("\n\n", lower, hard_end),
                normalized.rfind("\n", lower, hard_end),
                normalized.rfind(". ", lower, hard_end),
                normalized.rfind(" ", lower, hard_end),
            )
            boundary = max(candidates)
            if boundary > start:
                end = boundary + (2 if normalized[boundary:boundary + 2] in {"\n\n", ". "} else 1)
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(normalized):
            break
        next_start = max(start + 1, end - overlap)
        if next_start <= start:
            raise RuntimeError("chunker não avançou")
        start = next_start
    return chunks


def extract_metadata(title: str, text: str) -> dict:
    source = f"{title}\n{text}"
    upper = source.upper()
    audience = "Dev" if any(
        term in upper for term in ("TLPP", "ADVPL", "PONTO DE ENTRADA", "MSEXECAUTO", "API REST", "SDK")
    ) else "Funcional"
    if any(term in upper for term in ("COMO EMITIR", "PASSO A PASSO", "MANUAL DO USUARIO", "OPERACIONAL")):
        audience = "Usuario_Final"
    routines = {item.upper() for item in ROUTINE.findall(source)}
    entry_points = {item.upper() for item in EXPLICIT_ENTRY.findall(source)}
    if "PONTO DE ENTRADA" in title.upper():
        entry_points |= {
            item for item in {token.upper() for token in ROUTINE.findall(title)}
            if not item.startswith(PROGRAM_PREFIXES)
        }
    return {
        "modules": [name for name, pattern in MODULE_PATTERNS.items() if re.search(pattern, source, re.I)] or ["GERAL"],
        "tables": sorted({item.upper() for item in TABLE.findall(source)}),
        "parameters": sorted({item.upper() for item in PARAMETER.findall(source)}),
        "routines": sorted(routines),
        "entry_points": sorted(entry_points),
        "target_audience": audience,
    }


def process(pages: list[dict]) -> list[dict]:
    records: list[dict] = []
    for page in pages:
        text = (page.get("text") or "").strip()
        if not text:
            continue
        title = str(page.get("title", ""))
        chunks = split_text(text)
        metadata = extract_metadata(title, text)
        for index, chunk in enumerate(chunks):
            records.append({
                "id": f"TDN_{page['id']}_{index:03d}",
                "source_url": page.get("url", ""),
                "title": title,
                "chunk_index": index,
                "total_chunks": len(chunks),
                **metadata,
                "content": chunk,
            })
    return records


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pages_json", type=Path)
    parser.add_argument("output_jsonl", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        pages = json.loads(args.pages_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"não foi possível ler pages_json: {error}") from error
    if not isinstance(pages, list):
        raise SystemExit("pages_json deve conter uma lista JSON")
    records = process(pages)
    args.output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with args.output_jsonl.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(f"OK: {len(records)} chunks em {args.output_jsonl}")


if __name__ == "__main__":
    main()
