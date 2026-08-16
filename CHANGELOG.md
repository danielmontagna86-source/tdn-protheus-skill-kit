# Changelog

Todas as mudanças relevantes deste projeto serão registradas neste arquivo.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e o versionamento segue [Semantic Versioning](https://semver.org/lang/pt-BR/).

## [Unreleased]

### Fixed

- README principal corrigido para descrever o `tdn-protheus-skill-kit` como skill portátil de localização, coleta, processamento e manutenção de snapshots TDN, removendo a descrição herdada do servidor MCP.
- Histórico `0.2.0` corrigido para registrar somente funcionalidades pertencentes ao Skill Kit; o `tdn-protheus-mcp` permanece documentado como projeto complementar independente.

## [0.2.1] - 2026-08-16

### Fixed

- O localizador limitado de páginas TDN agora reinicia corretamente a paginação para cada página pai e rejeita links de paginação fora da API pública configurada.
- O prazo global de coleta e dry-run limita também atrasos e retentativas, evitando exceder o orçamento solicitado.

## [0.2.0] - 2026-08-15

### Added

- Instalação portátil da skill para Codex, Claude Code, Antigravity e loaders compatíveis com a convenção configurada para OpenRouter.
- Coleta controlada de documentação pública do TDN a partir de raízes escolhidas pela pessoa usuária.
- Snapshot local retomável com manifesto, páginas versionadas e exportação offline.
- Refresh incremental baseado em versão para baixar novamente somente páginas novas ou alteradas.
- Processamento de conteúdo para JSON/JSONL e chunks com metadados de contexto Protheus.
- Validação estrutural da skill, testes automatizados e empacotamento distribuível.

### Changed

- Dry-run de snapshot passou a aceitar prazo global e a devolver estimativa parcial estruturada ao atingir prazo ou limite de páginas, sem publicar snapshot incompleto.
- Adicionado `locate_tdn_pages.py` para descoberta paginada e limitada por metadados de título antes de criar snapshots de páginas específicas.
- Documentado o fluxo de uso conjunto com o projeto complementar `tdn-protheus-mcp`, mantendo instalação e responsabilidades separadas.

## [0.1.0] - 2026-08-15

### Added

- Skill portátil para Claude Code, Codex, Antigravity, OpenRouter e contexto Hermes Agent.
- Coleta TDN com processamento JSONL, snapshot local retomável, refresh incremental e exportação offline.
- Validação estrutural, testes unitários e empacotador ZIP.
- Proteção contra substituição silenciosa no instalador e exclusão de dados locais no pacote.
