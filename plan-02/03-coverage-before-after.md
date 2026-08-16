# Cobertura antes/depois

| Projeto/arquivo | Antes | Depois |
| --- | ---: | ---: |
| Skill total | 71% / 40 testes | 80% / 49 testes |
| `collect_tdn.py` | 58% | 89% |
| `sync_tdn_snapshot.py` | 67% | 75% |
| MCP total | 91% / 29 testes | 90% / 30 testes |

O gate do Skill foi elevado de 70% para 80%; MCP permaneceu no gate mais forte solicitado (90%). O sincronizador não alcançou a meta desejada de 78%; seu comportamento crítico foi ampliado e o resultado deve ser classificado como cobertura desejável parcial, não como falha do gate mínimo.
