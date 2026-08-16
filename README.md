# TDN Protheus MCP

MCP público e open source para pesquisar documentação TDN Protheus a partir de um **snapshot local controlado pela pessoa usuária**. Funciona por `stdio`, não exige token de LLM e não depende do Chat Protheus IA Lab.

O código usa Apache-2.0. A licença não transfere direitos sobre conteúdo, marcas ou serviços TOTVS/TDN; não publique snapshots nem dados de clientes.

## O que ele faz

- Pesquisa um índice SQLite FTS5 local e devolve citações (`source_url`, página e chunk).
- Expõe tools, resources e prompts MCP para Codex, Claude Code e hosts compatíveis com `stdio`.
- Inicia offline e read-only. Não baixa documentos durante consultas.
- O repositório e seu ZIP também incluem a skill de snapshot para obtenção e atualização explícita de conteúdo local.

Para localizar uma página dentro de uma raiz TDN ampla, a skill inclui `locate_tdn_pages.py`: descoberta limitada por metadados de títulos, com limites obrigatórios de profundidade, páginas, duração e candidatos. O fluxo recomendado é localizar → confirmar uma página candidata → `snapshot --max-depth 0` → indexar localmente; não use uma descoberta parcial como prova de ausência documental.

## Início rápido

Depois da publicação no PyPI:

```bash
uvx --from tdn-protheus-mcp tdn-protheus-mcp doctor --config ./tdn-protheus-mcp.config.json --json
uvx --from tdn-protheus-mcp tdn-protheus-mcp index --config ./tdn-protheus-mcp.config.json --root-id 235312129 --json
```

Copie `tdn-protheus-mcp.config.example.json`, altere `cache_root` e execute a skill de snapshot para criar o conteúdo local. Veja [instalação](docs/install.md), [segurança](docs/security.md) e o [contrato MCP](docs/mcp-protocol-contract.md).

## Clientes MCP

- [Claude Code](docs/configure-claude-code.md)
- [Codex](docs/configure-codex.md)
- [Configuração genérica](docs/configure-generic-mcp.md)

OpenRouter é um gateway/model provider, não um host MCP por si só. Use-o somente através de um cliente que implemente MCP `stdio`.

## Desenvolvimento

```bash
python -m pip install -e ".[snapshot]"
python -m unittest discover -s tests -p "test_*.py" -v
python -m build
python -m twine check dist/*
```

Não envie `tdn-cache/`, `.venv/`, snapshots, JSONL, HTML coletado, segredos ou dados de clientes. Consulte [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), [SUPPORT.md](SUPPORT.md) e [CHANGELOG.md](CHANGELOG.md).

## Skill portátil

A pasta `coletando-documentacao-tdn-protheus/` continua portável para Claude Code, Codex, Antigravity, loaders OpenRouter e fluxos Hermes. A documentação detalhada da skill está em seu próprio `SKILL.md`.
