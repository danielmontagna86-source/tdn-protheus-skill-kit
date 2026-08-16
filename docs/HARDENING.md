# Hardening e critérios de validação

Este documento descreve os invariantes que a branch `hardening/full-validation` deve provar antes de merge/release.

## Responsabilidade

- O Skill Kit é o único escritor do snapshot TDN.
- O repositório não contém implementação, pacote ou testes do MCP.
- O ZIP de release é montado por allowlist e não inclui cache, JSONL, `.venv` ou código MCP.

## Snapshot

- Novos snapshots usam schema v2 com geração imutável e `page_directory`.
- Snapshots v1 continuam legíveis e são migrados para v2 em refresh bem-sucedido.
- Escritas usam staging e troca atômica de manifesto.
- Uma falha ou timeout durante refresh preserva integralmente o snapshot ativo anterior.
- Apenas um escritor por `root_id` é aceito; locks não são removidos automaticamente.
- Estado parcial de snapshot exige `--resume` ou revisão explícita antes de nova escrita.
- Páginas removidas e páginas filtradas/stub não permanecem como conteúdo ativo antigo.

## Coleta

- Requests usam timeout e `allow_redirects=False`.
- Paginação é confinada à API pública TDN configurada.
- Links de página são confinados ao domínio TDN.
- Dry-run e refresh podem operar sob orçamento global de duração.

## Instalação

- A skill nova é validada e preparada em staging.
- Dependências são instaladas antes do swap.
- Falhas não substituem uma instalação anterior válida.

## Qualidade

- Matriz CI: Linux, Windows e macOS; Python 3.11 e 3.12.
- Validação estrutural, Ruff, testes, cobertura, auditoria de dependências, ZIP e SBOM.
- Live smoke limitado: página pública `SD1100I` -> snapshot v2 -> MCP -> citação; identificador inexistente -> zero evidência.

Nenhuma release deve ser criada enquanto algum gate obrigatório estiver vermelho.
