# Changelog

Todas as mudanças relevantes deste projeto serão registradas neste arquivo.

## [Unreleased]

### Changed

- Skill Kit separado fisicamente do MCP; removidos pacote, testes, metadata e documentação MCP duplicados.
- ZIP de release usa allowlist explícita e CI valida somente a skill.
- Snapshot schema v2 usa gerações imutáveis, `page_directory`, lock por raiz e publicação atômica.
- Refresh preserva integralmente o snapshot anterior em falhas e migra snapshots v1 para v2.
- Páginas alteradas que viram stubs passam a `filtered`, sem reutilizar conteúdo antigo.
- `--dry-run` e `--resume` passaram a ser mutuamente exclusivos.

## [0.2.1] - 2026-08-16

### Fixed

- Localizador reinicia corretamente a paginação para cada pai e rejeita links externos.
- Prazo global limita atrasos e retentativas no dry-run.

## [0.2.0] - 2026-08-15

### Added

- Skill portátil para agentes, coleta controlada, snapshot local, refresh incremental, JSON/JSONL e validação estrutural.
