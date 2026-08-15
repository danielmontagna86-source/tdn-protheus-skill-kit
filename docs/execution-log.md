# Diário de execução — TDN Protheus MCP público

Este documento é o registro operacional da execução de [architecture-public-tdn-protheus-mcp-sprints-1.md](../../plan/architecture-public-tdn-protheus-mcp-sprints-1.md). Ele deve ser atualizado ao iniciar e ao concluir cada sprint, com evidência de validação e bloqueios que dependam de decisão do responsável.

## Regras de execução

- Branch de trabalho: `feat/public-tdn-protheus-mcp`.
- Método: testes primeiro, implementação mínima, testes completos e revisão por sprint.
- O MCP público permanece independente do Chat Protheus IA Lab.
- O produto inicia local, offline e read-only; publicação PyPI, TestPyPI e serviço remoto exigem a autoridade externa indicada no roadmap.
- Não registrar snapshots, credenciais, conteúdo TDN ou dados pessoais neste documento.

## Andamento

| Sprint | Objetivo | Estado | Evidência / próximo marco |
|---|---|---|---|
| 0 | Base pública da skill | Concluída | Release `v0.1.0`, CI e 19 testes existentes. |
| 1 | Núcleo do pacote e política | Concluída | 27/27 testes aprovados em 2026-08-15; `doctor` offline, contratos, configuração, política e repositório read-only entregues. |
| 2 | Índice FTS5 e busca | Pendente | Inicia após contratos/configuração da Sprint 1. |
| 3 | MCP read-only por stdio | Pendente | Inicia após busca citável da Sprint 2. |
| 4 | Distribuição pública (MVP) | Pendente | PyPI só após validação local e TestPyPI. |
| 5 | Atualização controlada | Pendente | Requer núcleo MCP estável. |
| 6 | Adoção e qualidade | Pendente | Requer MVP instalável. |
| 7 | Decisão corporativa/remota | Pendente | Exige decisão explícita baseada em piloto. |

## Registro de eventos

| Data | Sprint | Evento | Resultado |
|---|---:|---|---|
| 2026-08-15 | 1 | Worktree isolado criado; `.worktrees/` incluído no `.gitignore`. | Branch pronta sem alterar a versão de produto em `main`. |
| 2026-08-15 | 1 | Baseline executado. Um teste assumia `.git` como diretório e falhava em worktree, onde ele é arquivo de ligação. | Teste tornado compatível com ambos os formatos; suíte: 19 aprovados. |
| 2026-08-15 | 1 | Núcleo MCP implementado com TDD. | Suíte completa: 27 aprovados; nenhuma chamada HTTP ou escrita de snapshot foi adicionada. |

## Decisões pendentes de autoridade externa

| Decisão | Quando será necessária | Ação até então |
|---|---|---|
| Criar/publicar pacote no TestPyPI/PyPI e configurar Trusted Publishing | Sprint 4, após pacote validado | Preparar workflow e artefatos, sem publicar. |
| Criar oferta remota HTTP/multiusuário | Sprint 7, após threat model e piloto | Não implementar endpoint remoto. |
