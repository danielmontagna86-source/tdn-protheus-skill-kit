# Changelog

Todas as mudanças relevantes deste projeto serão registradas neste arquivo.

## [0.3.1] - 2026-08-16

### Changed

- Plano 02: cobertura comportamental, Actions Node 24 por SHA e gates CodeQL/Dependency Review.
- Auditoria, SBOM, SHA256 e piso de build `setuptools>=83` passaram a integrar a validação.

## [0.3.0] - 2026-08-16

### Changed

- Skill Kit separado fisicamente do MCP e ZIP de release convertido para allowlist.
- Snapshot schema v2 com gerações imutáveis, lock por raiz e publicação atômica.
- Refresh preserva integralmente o snapshot anterior em falhas e migra v1 para v2.
- Coletor HTTP recusa redirects e paginação/links fora da origem pública TDN.
- Metadados Protheus reconhecem tabelas comuns, rotinas como `PLRSTPR1`, parâmetros e pontos de entrada como `SD1100I`.
- Instalador usa staging e rollback; falhas de validação/dependências não substituem a instalação anterior.
- Páginas que viram stubs recebem `filtered` e não mantêm conteúdo antigo ativo.
- Dependências de runtime foram reduzidas a `requests` e `beautifulsoup4`; o chunking é interno e determinístico.
- CI e release exigem Ruff, cobertura de branch mínima de 70%, auditoria de dependências, ZIP por allowlist e SBOM.

### Added

- Testes transacionais para rollback, lock, estado parcial, deadline de refresh e migração v1 → v2.
- Integração live limitada que coleta uma página pública TDN, gera snapshot v2, indexa com o MCP complementar e valida evidência/no-evidence.

## [0.2.1] - 2026-08-16

### Fixed

- Localizador reinicia corretamente a paginação para cada pai e rejeita links externos.
- Prazo global limita atrasos e retentativas no dry-run.

## [0.2.0] - 2026-08-15

### Added

- Skill portátil, coleta controlada, snapshot local, refresh incremental, JSON/JSONL e validação estrutural.
