# TDN Protheus Skill Kit

Skill portátil e open source para **localizar, coletar, processar e manter snapshots locais de documentação técnica pública do TDN Protheus** para uso como contexto por agentes de IA.

O projeto é independente do [`tdn-protheus-mcp`](https://github.com/danielmontagna86-source/tdn-protheus-mcp). A skill prepara e atualiza a base documental; o MCP complementar pode indexar esse snapshot local e disponibilizar busca citável via protocolo MCP `stdio`.

O código usa Apache-2.0. A licença não transfere direitos sobre conteúdo, marcas ou serviços TOTVS/TDN. Não publique snapshots, HTML coletado, exports de documentação ou dados de clientes.

## O que este projeto faz

- Localiza páginas candidatas em raízes TDN amplas usando apenas metadados de título e limites explícitos.
- Coleta documentação pública do TDN a partir de raízes ou páginas escolhidas pela pessoa usuária.
- Mantém snapshot local retomável, com refresh incremental e exportação offline.
- Converte o conteúdo coletado em JSON/JSONL e chunks com metadados úteis para contexto e RAG.
- Valida a estrutura da skill e oferece instalador para diferentes harnesses de agentes.
- Mantém a obtenção da documentação separada da consulta por agentes.

## O que este projeto não faz

- Não é um servidor MCP.
- Não cria índice SQLite FTS5.
- Não expõe tools MCP por `stdio`.
- Não conecta no ERP, banco de dados, AppServer ou RPO do cliente.
- Não deve ser usado para redistribuir conteúdo da TOTVS/TDN.

Para busca local citável por agentes, use o projeto complementar [`tdn-protheus-mcp`](https://github.com/danielmontagna86-source/tdn-protheus-mcp).

## Estrutura principal

```text
coletando-documentacao-tdn-protheus/
├── SKILL.md
├── requirements.txt
└── scripts/
    ├── collect_tdn.py
    ├── locate_tdn_pages.py
    ├── process_tdn.py
    ├── sync_tdn_snapshot.py
    └── validate_skill.py
```

## Fluxo recomendado

```text
Documentação pública TDN
          ↓
Localização controlada de páginas
          ↓
Skill: coleta / snapshot / refresh
          ↓
Snapshot local
          ↓
Export JSON/JSONL ou MCP complementar
          ↓
Agente de IA
          ↓
Validação humana
```

## Início rápido

Requer Python 3.11+.

Clone o repositório:

```bash
git clone https://github.com/danielmontagna86-source/tdn-protheus-skill-kit.git
cd tdn-protheus-skill-kit
```

Antes de instalar, faça uma prévia:

```bash
python install.py --platform codex --scope project --dry-run
```

Depois instale no projeto atual:

```bash
python install.py --platform codex --scope project
```

Valores suportados pelo instalador incluem:

- `codex`
- `claude`
- `antigravity`
- `openrouter` para loaders que seguem a convenção de skills compatível

Use `--scope user` quando quiser instalar no perfil da pessoa usuária. Não use `--force` sem revisar uma instalação existente.

## Localizar antes de coletar

Quando a raiz TDN for ampla, localize primeiro páginas candidatas sem baixar `body.storage`:

```bash
python coletando-documentacao-tdn-protheus/scripts/locate_tdn_pages.py \
  --root-id 811253174 \
  --term MATA103 \
  --term SD1100I \
  --term PLRSTPR1 \
  --max-depth 1 \
  --max-list-pages 100 \
  --max-duration-seconds 120 \
  --max-candidates 20 \
  --delay 0.35 \
  --json
```

O resultado informa `complete`, `stop_reason`, `list_pages_fetched`, `nodes_seen`, `candidates` e `next_cursor_available`.

`complete: false` significa que a descoberta foi parcial. Uma descoberta parcial **não é prova de ausência documental**.

Depois de confirmar uma página candidata, prefira um snapshot específico com `--max-depth 0` quando isso for suficiente para o caso de uso.

## Criar um snapshot local

Entre na pasta da skill instalada ou use os scripts diretamente no clone.

Faça primeiro um dry-run limitado:

```bash
python scripts/sync_tdn_snapshot.py snapshot \
  --root-id 235312129 \
  --cache-dir ./tdn-cache \
  --max-depth 8 \
  --max-duration-seconds 120 \
  --dry-run
```

Em árvores amplas, o dry-run pode terminar com `complete: false` por `max-duration` ou `max-pages`. Nesse caso, escolha uma raiz mais específica antes de iniciar uma coleta real.

Para criar o snapshot:

```bash
python scripts/sync_tdn_snapshot.py snapshot \
  --root-id 235312129 \
  --cache-dir ./tdn-cache \
  --max-depth 8 \
  --checkpoint-every 25
```

Interrupções podem ser retomadas com `--resume` quando aplicável.

## Atualizar e exportar offline

Refresh incremental:

```bash
python scripts/sync_tdn_snapshot.py refresh \
  --root-id 235312129 \
  --cache-dir ./tdn-cache \
  --max-depth 8
```

Export offline:

```bash
python scripts/sync_tdn_snapshot.py export \
  --root-id 235312129 \
  --cache-dir ./tdn-cache \
  --output-dir ./saida-local \
  --offline
```

Processamento para chunks JSONL:

```bash
python scripts/process_tdn.py \
  ./saida-local/tdn_pages.json \
  ./saida-local/tdn_chunks.jsonl
```

## Uso com o TDN Protheus MCP

A skill e o MCP são projetos separados, mas podem compartilhar o mesmo snapshot local.

```text
Skill Kit
   ↓
cache_root/<root_id>/manifest.json + pages/
   ↓
TDN Protheus MCP
   ↓
SQLite FTS5 + busca + contexto + citações
```

Ao usar os dois juntos:

1. configure um `cache_root` absoluto;
2. use o mesmo caminho na skill e no MCP;
3. crie ou atualize o snapshot com a skill;
4. execute novamente `tdn-protheus-mcp index` após cada snapshot/refresh;
5. mantenha o MCP em `offline=true` e `allow_mutations=false` quando quiser apenas consulta local.

Guia complementar no MCP: [`docs/companion-skill.md`](https://github.com/danielmontagna86-source/tdn-protheus-mcp/blob/main/docs/companion-skill.md).

## Segurança e limites

- Não contorne autenticação, CAPTCHA, bloqueios ou limites do TDN.
- Use raízes específicas e limites de profundidade, páginas e duração.
- Não conclua ausência documental a partir de descoberta parcial.
- Não envie `tdn-cache/`, HTML bruto, JSONL coletado, `.venv`, segredos ou dados de clientes ao Git.
- Trate documentação pública recuperada como referência externa que ainda exige validação técnica.
- Confirme release, contexto do ambiente e customizações antes de implementar código no ERP.

## Validação e desenvolvimento

Valide a estrutura da skill:

```bash
python coletando-documentacao-tdn-protheus/scripts/validate_skill.py coletando-documentacao-tdn-protheus
```

Execute os testes:

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

Consulte também:

- [`coletando-documentacao-tdn-protheus/SKILL.md`](coletando-documentacao-tdn-protheus/SKILL.md)
- [`CONTRIBUTING.md`](CONTRIBUTING.md)
- [`SECURITY.md`](SECURITY.md)
- [`SUPPORT.md`](SUPPORT.md)
- [`CHANGELOG.md`](CHANGELOG.md)

## Projeto complementar

**TDN Protheus MCP**  
https://github.com/danielmontagna86-source/tdn-protheus-mcp

Use a skill para preparar a base documental. Use o MCP quando quiser consultar essa base localmente por agentes compatíveis com MCP e recuperar contexto com origem rastreável.
