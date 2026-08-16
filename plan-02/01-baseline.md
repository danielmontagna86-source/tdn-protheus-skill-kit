# Plano 02 — Baseline

Data: 2026-08-16. Nenhuma alteração foi feita na `main`.

| Projeto | commit main | VERSION | testes | cobertura |
| --- | --- | --- | ---: | ---: |
| Skill Kit | `8c964b1` | 0.3.0 | 40 | 71% |
| MCP | `53e171c` | 0.4.0 | 29 | 91% |

Python suportado: 3.11 e 3.12 em ambos. Skill: `collect_tdn.py` 58%, `sync_tdn_snapshot.py` 67%. MCP: gate já era 75%, cobertura medida 91%.

Workflows observados: CI 3 SO x 2 Python, release; Skill também Live TDN; MCP também PyPI. CodeQL e Dependency Review não existiam. Ações sem SHA e/ou runtime antigo incluíam upload/download-artifact. O warning `IncompleteFieldDefinitionWarning` foi reproduzido no MCP 1.29.0 + pydantic 2.13.4 + pydantic-settings 2.15.0 em Python 3.12.
