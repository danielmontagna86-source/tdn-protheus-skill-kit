# Cobertura antes/depois

| Projeto/arquivo | Antes | Depois |
| --- | ---: | ---: |
| Skill total | 71% / 40 testes | 80% / 49 testes |
| `collect_tdn.py` | 58% | 89% |
| `sync_tdn_snapshot.py` | 67% | 75% |
| MCP total | 91% / 29 testes | 90% / 30 testes |

O gate do Skill foi elevado de 70% para 80%; MCP permaneceu no gate mais forte solicitado (90%). O sincronizador não alcançou a meta desejada de 78%; seu comportamento crítico foi ampliado e o resultado deve ser classificado como cobertura desejável parcial, não como falha do gate mínimo.

| Controle | Antes | Depois |
| --- | --- | --- |
| Warnings Node 20 sob controle | ações antigas/não pinadas | Actions Node 24 por SHA; CI hospedada PASS |
| Warning MCP `IncompleteFieldDefinitionWarning` | reproduzido | eliminado por `FastMCPSettings.model_rebuild()`; teste e stdio PASS |
| CodeQL | Default Setup existente, sem evidência de severidade | Default Setup + `CodeQL Alert Gate` PASS nos dois PRs |
| Dependency Review | ausente | PASS no Skill e MCP, severidade `moderate` |
| Supply chain | sem piso explícito de regressão | `setuptools>=83`, audit, SBOM e SHA256 PASS |
