"""Transforma tdn_pages.json em chunks JSONL com metadados Protheus."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter

MODULE_PATTERNS = {
    "ADVPL": r"\b(ADVPL|TLPP|PO-?UI|POUI|EXEC_AUTO|MSEXECAUTO|RESTMODEL|USER\s*FUNCTION)\b",
    "SIGAFAT": r"\b(SIGAFAT|FATURAMENTO|MATA410|MATA460|MATA461|SC5|SC6|SF2|SD2)\b",
    "SIGACOM": r"\b(SIGACOM|COMPRAS|MATA110|MATA120|MATA103|SC1|SC7|SF1|SD1)\b",
    "SIGAEST": r"\b(SIGAEST|ESTOQUE|CUSTO\s*MEDIO|MATA240|MATA330|SB1|SB2|SD3)\b",
    "SIGAFIN": r"\b(SIGAFIN|FINANCEIRO|FINA040|FINA050|SE1|SE2|SE5)\b",
    "SIGACTB": r"\b(SIGACTB|CONTABILIDADE|CTBA102|CTBA105|CT1|CT2)\b",
    "SIGAFIS": r"\b(SIGAFIS|FISCAL|SPED|FISA001|SF3|SFT|SF4)\b",
    "SIGAATF": r"\b(SIGAATF|ATIVO\s*FIXO|ATFA012|ATFA050|SN1|SN3)\b",
    "SIGAGCT": r"\b(SIGAGCT|CONTRATOS|CNTA300|CNTA120|CN9|CNC|CND)\b",
    "TRIBUTARIO": r"\b(REFORMA\s*TRIBUTARIA|IBS|CBS|FISA170|F0L|F0M|F0P)\b",
}
TABLE = re.compile(r"\b(?:S[A-Z]{2}|F0[A-Z0-9]|CN[A-Z0-9]|CT[0-9]|SN[1-5])\b")
PARAMETER = re.compile(r"\bMV_[A-Z0-9_]{3,}\b", re.I)
ROUTINE = re.compile(r"\b(?:MATA|FINA|CTBA|FISA|ATFA|CNTA|SPED)[A-Z0-9]{3,}\b", re.I)
ENTRY_POINT = re.compile(r"\b(?:ADV[0-9]+_PE_[A-Z0-9_]+|[A-Z0-9]{3,}_PE(?:_[A-Z0-9_]+)?)\b", re.I)


def extract_metadata(title: str, text: str) -> dict:
    source = f"{title}\n{text}"
    upper = source.upper()
    audience = "Dev" if any(term in upper for term in (
        "TLPP", "ADVPL", "PONTO DE ENTRADA", "MSEXECAUTO", "API REST", "SDK"
    )) else "Funcional"
    if any(term in upper for term in (
        "COMO EMITIR", "PASSO A PASSO", "MANUAL DO USUARIO", "OPERACIONAL"
    )):
        audience = "Usuario_Final"
    return {
        "modules": [name for name, pattern in MODULE_PATTERNS.items() if re.search(pattern, source, re.I)] or ["GERAL"],
        "tables": sorted(set(TABLE.findall(upper))),
        "parameters": sorted({item.upper() for item in PARAMETER.findall(source)}),
        "routines": sorted({item.upper() for item in ROUTINE.findall(source)}),
        "entry_points": sorted({item.upper() for item in ENTRY_POINT.findall(source)}),
        "target_audience": audience,
    }


def process(pages: list[dict]) -> list[dict]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1200,
        chunk_overlap=200,
        separators=["\n## ", "\n### ", "\n#### ", "\n\n", "\n", " ", ""],
    )
    records: list[dict] = []
    for page in pages:
        text = (page.get("text") or "").strip()
        if not text:
            continue
        title = page.get("title", "")
        chunks = splitter.split_text(text)
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
    parser.add_argument("pages_json", type=Path, help="Arquivo tdn_pages.json")
    parser.add_argument("output_jsonl", type=Path, help="Arquivo JSONL de chunks")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    pages = json.loads(args.pages_json.read_text(encoding="utf-8"))
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
