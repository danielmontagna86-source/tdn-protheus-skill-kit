# Skill portátil — TDN Protheus

Este kit contém uma única skill no padrão `SKILL.md`, mais scripts Python opcionais. Copie a pasta `coletando-documentacao-tdn-protheus` inteira, sem alterar seu conteúdo, para um dos destinos abaixo.

| Ambiente | Destino de projeto | Destino global |
|---|---|---|
| Claude Code | `.claude/skills/` | `~/.claude/skills/` |
| Codex | `.codex/skills/` | `~/.codex/skills/` |
| Antigravity | `.agents/skills/` | `~/.gemini/config/skills/` |
| OpenRouter | diretório configurado pelo loader | o mesmo diretório do loader |

Exemplos de destino final:

```text
.claude/skills/coletando-documentacao-tdn-protheus/SKILL.md
.codex/skills/coletando-documentacao-tdn-protheus/SKILL.md
.agents/skills/coletando-documentacao-tdn-protheus/SKILL.md
```

No OpenRouter, uma pasta não é descoberta por si só: configure seu agente/loader para expor e injetar o `SKILL.md`. O exemplo oficial do Agent SDK usa `~/.claude/skills/`, portanto essa localização funciona quando esse loader é adotado.

## Instalação e teste

```bash
pip install -r requirements.txt
python coletando-documentacao-tdn-protheus/scripts/validate_skill.py coletando-documentacao-tdn-protheus
python coletando-documentacao-tdn-protheus/scripts/collect_tdn.py --help
python coletando-documentacao-tdn-protheus/scripts/process_tdn.py --help
```

Depois, abra uma conversa e peça para “coletar documentação AdvPL do TDN” ou invoque a skill pelo nome, quando a plataforma oferecer invocação explícita.

## Cache local e operação offline

O instalador **não** baixa documentação. Para uma cópia local reutilizável, entre na pasta `coletando-documentacao-tdn-protheus` e use o Python do `.venv` criado pelo instalador.

Primeiro, estime a coleta. Isto somente percorre a árvore e não baixa corpos nem grava cache:

```bash
# Windows
.venv\Scripts\python.exe scripts\sync_tdn_snapshot.py snapshot --root-id 235312129 --cache-dir .\tdn-cache --max-depth 8 --dry-run
```

O snapshot inicial de Protheus 12 pode levar 30–50 minutos ou mais. Faça-o apenas com espaço livre e tempo disponível; use uma raiz específica (AdvPL, Parâmetros ou Pontos de Entrada) no piloto.

```bash
.venv\Scripts\python.exe scripts\sync_tdn_snapshot.py snapshot --root-id 235312129 --cache-dir .\tdn-cache --max-depth 8 --checkpoint-every 25
.venv\Scripts\python.exe scripts\sync_tdn_snapshot.py export --root-id 235312129 --cache-dir .\tdn-cache --output-dir .\saida-local --offline
```

Depois disso, `export --offline` não cria conexão HTTP. Para atualizar periodicamente, execute `refresh` com a mesma raiz/cache; ele compara versão de cada página e baixa corpo apenas para páginas novas ou alteradas. Use `snapshot --resume` após interrupção.

Não compartilhe `tdn-cache/` nem `.venv/`: ambos ficam excluídos do pacote de distribuição.

## Compatibilidade deliberada

O frontmatter usa apenas `name` e `description`, que são compatíveis com o núcleo do padrão. Não inclui campos exclusivos de Claude Code, Codex, Antigravity ou OpenRouter. Os scripts dependem apenas de Python e dos pacotes em `requirements.txt`.

## Limites

Os endpoints, permissões públicas e limites do TDN podem mudar; valide um piloto antes de uma coleta ampla. O kit não inclui, transmite ou licencia conteúdo da TOTVS.

## Hermes Agent

Hermes é um formato de saída, não uma plataforma de instalação. Após uma coleta ou um export local offline, processe o arquivo `tdn_pages.json` com `scripts/process_tdn.py`. O JSONL resultante contém uma linha por chunk e os campos `id`, `source_url`, `title`, `chunk_index`, `total_chunks`, `modules`, `tables`, `parameters`, `routines`, `entry_points`, `target_audience` e `content`.

## Segurança e direitos

- O instalador não substitui uma skill existente sem `--force` explícito.
- Não envie ao repositório `tdn-cache/`, `.venv/`, saídas `saida-*`, JSON/JSONL coletado, HTML bruto, dados de clientes ou credenciais.
- O código é licenciado sob Apache-2.0. Isso não licencia conteúdo do TDN, marcas ou produtos da TOTVS; consulte [NOTICE.md](NOTICE.md).
- Relate vulnerabilidades conforme [SECURITY.md](SECURITY.md), nunca por issue público com dados sensíveis.

## Desenvolvimento

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
python package.py --output dist/tdn-protheus-skill-kit.zip
```

Leia [CONTRIBUTING.md](CONTRIBUTING.md), [SUPPORT.md](SUPPORT.md) e [CHANGELOG.md](CHANGELOG.md) antes de contribuir.
