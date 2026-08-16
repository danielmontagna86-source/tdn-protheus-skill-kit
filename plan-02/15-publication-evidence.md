# Plano 02 — Evidências

## O que foi testado

Coletor HTTP/HTML/domínios/deadline; snapshot v1/v2/rollback/resume/lock; MCP stdio/index/search/stale; artefatos e auditoria.

## Por que fizemos este ciclo

Elevar cobertura comportamental, preservar atomicidade do snapshot, tratar warnings, atualizar runtimes de Actions e inserir gates de segurança.

## Baseline

Skill 40 testes/71%; MCP 29 testes/91%.

## Mudanças realizadas

Skill 49 testes/80%, ações Node 24 por SHA, CodeQL, Dependency Review e piso setuptools 83. MCP eliminou warning por `model_rebuild`, adicionou teste de regressão e os mesmos gates. O CodeQL Default Setup foi mantido e recebeu um gate de alertas High/Critical por API oficial.

## Teste prático 1 — evidência real

Comando/pergunta: snapshot da raiz 908337356; index; search `SD1100I`/routine `SD1100I`.
Resultado: PASS.
Evidência: page 908337356, chunk 908337356:0, generation e fingerprint em `12-live-test.md`.

## Teste prático 2 — informação inexistente

Comando/pergunta: `SD1100I` com routine `MT103VALIDAITENSXYZ`.
Resultado: 0 evidências, PASS.
Evidência: `12-live-test.md`.

## Teste prático 3 — índice stale

Comando: troca controlada A→B sem reindexar.
Resultado: `POLICY_INDEX_STALE`, depois B indexada, PASS.
Evidência: `13-stale-index-test.md`.

## Teste prático 4 — rollback

Comando: refresh com falha controlada depois de uma página.
Resultado: manifest e bytes ativos inalterados; staging não ativa, PASS.
Evidência: `05-snapshot-tests.md`.

## Números antes/depois

Em `03-coverage-before-after.md`.

## Problemas encontrados durante o trabalho

Warning Pydantic no MCP; Actions de artifact antigas/não pinadas; ausência de CodeQL/Dependency Review.

## Problemas corrigidos

Warning eliminado; ações atualizadas; gates e testes adicionados.

## Problemas upstream

Nenhum bloqueio confirmado localmente. O Dependency Graph inicialmente desabilitado no MCP foi habilitado; o Dependency Review oficial passou na tentativa 2 do run `31978377887`.

## Limitações

A matriz GitHub concluiu PASS em Windows, Ubuntu e macOS com Python 3.11/3.12. CodeQL Advanced não pode coexistir com o Default Setup já habilitado pela plataforma; o workflow redundante foi removido. O `CodeQL Alert Gate` consulta a API oficial sob `security-events: read` e comprovou zero alertas abertos High/Critical no momento de cada run.

## Commits exatos

Baseline Skill `8c964b1`; MCP `53e171c`. Commits de verificação CodeQL: Skill `724a1145`; MCP `4fe5ee11`.

## PRs

[Skill PR #10](https://github.com/danielmontagna86-source/tdn-protheus-skill-kit/pull/10) e [MCP PR #12](https://github.com/danielmontagna86-source/tdn-protheus-mcp/pull/12), ambos draft e sem merge.

## Resultado final

PASS.

## Conclusão técnica

Os controles locais, a matriz hospedada e os laboratórios obrigatórios passaram. Não houve P0/P1 novo identificado. Os PRs permanecem sem merge para revisão humana.
