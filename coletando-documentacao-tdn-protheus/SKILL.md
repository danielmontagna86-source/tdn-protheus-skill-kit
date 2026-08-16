---
name: coletando-documentacao-tdn-protheus
description: Use quando precisar buscar, atualizar ou preparar um dataset de documentação técnica pública do Protheus no TDN/TOTVS Confluence, incluindo AdvPL, parâmetros, pontos de entrada, Documento de Referência ou JSONL de contexto para Hermes Agent.
---

# Coletando documentação do TDN Protheus

Use esta skill para coletar documentação pública via API REST do Confluence do TDN. Prefira raízes documentais a varrer o espaço inteiro. Preserve URL e data de coleta; use o resultado somente como contexto interno, sem redistribuir conteúdo da TOTVS.

## Dependências e segurança

- Python 3.11, `requests` e `beautifulsoup4`; para chunks, `langchain-text-splitters`. Instale com `pip install -r requirements.txt` na raiz do kit.
- A API observada é `https://tdn.totvs.com/rest/api`, acessível anonimamente no momento da coleta. Confirme isso no ambiente de execução; não contorne autenticação, CAPTCHA, bloqueio ou limites.
- Use timeout de 30 s, três tentativas, backoff, `User-Agent` de navegador e atraso de 0,35 s por página.

## Raízes úteis

| ID | Conteúdo |
|---:|---|
| `237387586` | Protheus 12 — Documento de Referência |
| `235312129` | AdvPL |
| `811253122` | Parâmetros |
| `811253174` | Pontos de Entrada |

Comece pelas três últimas em pilotos. O crawl completo de Protheus 12 é amplo e pode levar 30–50 minutos ou mais. O piloto AdvPL analisado continha 98 páginas úteis, mas a contagem não é garantia futura.

## Executar

1. Faça um piloto de AdvPL:

   ```bash
   python scripts/collect_tdn.py 235312129 ./saida-advpl --max-depth 8
   ```

2. O coletor descobre filhos por `GET /content/{id}/child/page?limit=50&start=N`, segue `_links.next` quando fornecido e usa o avanço por `start` como fallback. Para cada página, chama `GET /content/{id}?expand=body.storage`.

3. Ele converte HTML storage em texto, remove `script`, `style`, `footer` e `aside`, preserva tabelas como `célula | célula`, descarta textos menores que 60 caracteres e grava `tdn_pages.json`, `tdn_pages.jsonl` e `tdn_errors.jsonl`.

4. Para metadados e chunks JSONL para RAG, execute:

   ```bash
   python scripts/process_tdn.py ./saida-advpl/tdn_pages.json ./saida-advpl/tdn_chunks.jsonl
   ```

   O processador gera `id`, `source_url`, `title`, `chunk_index`, `total_chunks`, `modules`, `tables`, `parameters`, `routines`, `entry_points`, `target_audience` e `content`.

## Uso com Hermes Agent

Não instale integração adicional nem altere o destino da skill. Quando a solicitação for preparar contexto para o Hermes Agent, use o mesmo `scripts/process_tdn.py` após uma coleta online ou um `export --offline` local. O JSONL já segue o contrato Hermes, com uma linha por chunk e exatamente estes campos:

```text
id, source_url, title, chunk_index, total_chunks, modules, tables,
parameters, routines, entry_points, target_audience, content
```

Fluxo Hermes com cache local:

```bash
python scripts/sync_tdn_snapshot.py export --root-id 235312129 --cache-dir ./tdn-cache --output-dir ./saida-hermes --offline
python scripts/process_tdn.py ./saida-hermes/tdn_pages.json ./saida-hermes/hermes_tdn_chunks.jsonl
```

Antes de entregar ao Hermes, valide que o arquivo não está vazio, cada linha é JSON válido, todos os campos acima existem e `content` contém texto. Não envie `tdn-cache/`, HTML bruto, `.venv` ou materiais privados: somente o JSONL de chunks revisado.

## Snapshot local e atualização periódica

Para trabalhar sem rede depois da primeira coleta, use `scripts/sync_tdn_snapshot.py`. O cache é sempre limitado a uma raiz escolhida; não existe modo para baixar o espaço `PROT` inteiro.

### Localizar antes de coletar uma raiz ampla

Quando a raiz possui muitos filhos, primeiro use `scripts/locate_tdn_pages.py`. Ele consulta somente os metadados paginados de `child/page`; não baixa `body.storage` e nunca deve substituir um snapshot. Todos os limites são obrigatórios para manter a descoberta controlada:

```bash
python scripts/locate_tdn_pages.py --root-id 811253174 --term MATA103 --term SD1100I --term PLRSTPR1 --max-depth 1 --max-list-pages 100 --max-duration-seconds 120 --max-candidates 20 --delay 0.35 --json
```

O resultado tem `complete`, `stop_reason`, `list_pages_fetched`, `nodes_seen`, `candidates` e `next_cursor_available`. `complete: false` significa descoberta incompleta: registre o cursor/limite e não conclua que o documento não existe. Confirme o conteúdo de cada candidato com uma única leitura pública antes de criar um snapshot individual com `--max-depth 0`.

1. Estime antes de baixar. Isto navega a árvore, mas não baixa corpos nem grava cache:

   ```bash
   python scripts/sync_tdn_snapshot.py snapshot --root-id 235312129 --cache-dir ./tdn-cache --max-depth 8 --max-duration-seconds 120 --dry-run
   ```

2. Inicie o snapshot somente após revisar a estimativa. Protheus 12 pode levar 30–50 minutos ou mais e ocupar espaço considerável. Interrupções podem ser retomadas com `--resume`:

   ```bash
   python scripts/sync_tdn_snapshot.py snapshot --root-id 235312129 --cache-dir ./tdn-cache --max-depth 8 --checkpoint-every 25
   ```

   Em árvores amplas, mantenha `--max-duration-seconds` no dry-run. Se o prazo ou `--max-pages` for atingido, ele devolve JSON com `complete: false`; não inicia a coleta nem publica manifesto parcial. Escolha uma página-raiz mais específica antes de fazer o snapshot real.

3. Gere a saída sem HTTP e processe-a normalmente:

   ```bash
   python scripts/sync_tdn_snapshot.py export --root-id 235312129 --cache-dir ./tdn-cache --output-dir ./saida-local --offline
   python scripts/process_tdn.py ./saida-local/tdn_pages.json ./saida-local/tdn_chunks.jsonl
   ```

4. Atualize periodicamente. O refresh percorre a árvore e compara `version.number`/`version.when`; só baixa o corpo de páginas novas ou alteradas. Páginas removidas ficam no histórico e saem do export padrão:

   ```bash
   python scripts/sync_tdn_snapshot.py refresh --root-id 235312129 --cache-dir ./tdn-cache --max-depth 8
   ```

## Regras de operação

- `expand=body.storage` é obrigatório: o corpo está em `body.storage.value`, em HTML do Confluence, não Markdown.
- Trate `404` como página removida/inexistente e continue. Falhas finais de rede não podem parecer fim de paginação: registre e pare o crawl para revisão.
- Não confie apenas em `size`: ele pode representar a página atual. Priorize `_links.next`; sem cursor, continue enquanto o lote estiver cheio.
- O filtro de 60 caracteres remove stubs, não ruído semântico. Sinais de ruído incluem títulos `DMAN`/`DT`, `CONTEÚDO INTERNO TOTVS` e registros DACI. Prefira uma raiz específica e revise amostras.
- Não misture esta fonte pública com materiais privados ou `owner_confirmed` de outro `source_id`.

## Verificar antes de usar o dataset

- Entre na pasta da skill e valide: `python scripts/validate_skill.py .`.
- Confira que a lista de páginas não está vazia, URLs pertencem ao domínio TDN e todo texto retido tem pelo menos 60 caracteres.
- Conte páginas, chunks, bytes de corpo, erros finais e distribuição de módulos. Investigue muitos chunks `GERAL`.
- Faça inspeção manual de páginas com tabelas e de uma página em cada profundidade. Registre raiz, profundidade, data e versão do script junto ao dataset.

## Recursos

- `scripts/collect_tdn.py`: coletor reexecutável; comece por `--help`.
- `scripts/locate_tdn_pages.py`: descoberta limitada por metadados de título; use antes de coletar raízes amplas.
- `scripts/process_tdn.py`: regex Protheus e chunking; execute somente após revisar a coleta.
- `scripts/sync_tdn_snapshot.py`: snapshot local, refresh incremental, export offline e status; comece por `--help` e `snapshot --dry-run`.
- `scripts/validate_skill.py`: contrato estrutural do pacote; não acessa a rede.
