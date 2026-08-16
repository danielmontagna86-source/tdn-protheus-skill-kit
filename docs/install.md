# Instalação — TDN Protheus Skill Kit

Requisito: Python 3.11+.

Clone o repositório e faça primeiro uma prévia:

```bash
git clone https://github.com/danielmontagna86-source/tdn-protheus-skill-kit.git
cd tdn-protheus-skill-kit
python install.py --platform codex --scope project --dry-run
```

Depois instale:

```bash
python install.py --platform codex --scope project
```

Plataformas aceitas pelo instalador: `codex`, `claude`, `antigravity` e `openrouter` para loaders compatíveis com a convenção documentada.

O instalador copia somente `coletando-documentacao-tdn-protheus/`, valida a skill e cria uma `.venv` local para as dependências. Use `--skip-deps` somente quando o ambiente Python já estiver preparado.

O MCP complementar é instalado separadamente a partir de https://github.com/danielmontagna86-source/tdn-protheus-mcp.
