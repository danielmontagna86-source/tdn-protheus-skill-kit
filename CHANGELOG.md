# Changelog

Todas as mudanças relevantes deste projeto serão registradas neste arquivo.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e o versionamento segue [Semantic Versioning](https://semver.org/lang/pt-BR/).

## [0.2.1] - 2026-08-16

### Fixed

- O localizador limitado de páginas TDN agora reinicia corretamente a paginação para cada página pai e rejeita links de paginação fora da API pública configurada.
- O prazo global de coleta e dry-run limita também atrasos e retentativas, evitando exceder o orçamento solicitado.

## [0.2.0] - 2026-08-15

### Added

- Pacote público `tdn-protheus-mcp` com CLI, configuração segura e índice SQLite FTS5 local.
- Servidor MCP `stdio` read-only com tools, resources, prompts e citações rastreáveis.
- Guias de instalação e configuração para Claude Code, Codex e hosts MCP genéricos.
- Contrato de protocolo, documentação de segurança e decisão de distribuição.

### Changed

- Dry-run de snapshot agora aceita prazo global e devolve estimativa parcial estruturada ao atingir prazo ou limite de páginas, sem publicar snapshot incompleto.
- Adicionado `locate_tdn_pages.py` para descoberta paginada e limitada por metadados de título antes de criar snapshots de páginas específicas.

## [0.1.0] - 2026-08-15

### Added

- Skill portátil para Claude Code, Codex, Antigravity, OpenRouter e contexto Hermes Agent.
- Coleta TDN com processamento JSONL, snapshot local retomável, refresh incremental e exportação offline.
- Validação estrutural, testes unitários e empacotador ZIP.
- Proteção contra substituição silenciosa no instalador e exclusão de dados locais no pacote.
