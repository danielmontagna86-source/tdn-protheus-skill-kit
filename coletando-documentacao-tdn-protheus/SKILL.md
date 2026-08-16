---
name: coletando-documentacao-tdn-protheus
description: Use quando precisar localizar, coletar, atualizar ou preparar documentação técnica pública do Protheus no TDN, incluindo AdvPL, parâmetros, pontos de entrada e snapshots locais para agentes de IA.
---

# Coletando documentação do TDN Protheus

Use esta skill como **único escritor do snapshot local**. O MCP complementar apenas lê e indexa esse snapshot.

## Segurança e dependências

- Python 3.11+, `requests` e `beautifulsoup4`. O chunking JSONL é implementado pelo próprio projeto, sem framework de RAG adicional.
- API pública observada: `https://tdn.totvs.com/rest/api`.
- Não contorne autenticação, CAPTCHA, bloqueios ou limites.
- Use raízes específicas, delays, limites de páginas/profundidade e dry-run antes de coletas amplas.

## Raízes úteis

| ID | Conteúdo |
|---:|---|
| `237387586` | Protheus 12 — Documento de Referência |
| `235312129` | AdvPL |
| `811253122` | Parâmetros |
| `811253174` | Pontos de Entrada |

## Localizar antes de coletar

```bash
python scripts/locate_tdn_pages.py --root-id 811253174 --term MATA103 --term SD1100I --term PLRSTPR1 --max-depth 1 --max-list-pages 100 --max-duration-seconds 120 --max-candidates 20 --delay 0.35 --json
```

`complete: false` significa descoberta incompleta e nunca deve ser interpretado como prova de ausência.

## Snapshot schema v2

Novos snapshots são publicados por geração imutável:

```text
cache_root/<root_id>/
├── manifest.json
└── generations/<generation_id>/pages/<page_id>.json
```

O manifesto usa `schema_version: 2`, `generation_id` e `page_directory`. Snapshots v1 antigos em `pages/` continuam legíveis e são migrados para v2 no próximo refresh bem-sucedido.

A publicação é transacional: páginas são preparadas em staging e o manifesto só muda quando a geração está completa. Uma falha no meio do refresh preserva integralmente o snapshot ativo anterior.

## Criar snapshot

```bash
python scripts/sync_tdn_snapshot.py snapshot --root-id 235312129 --cache-dir ./tdn-cache --max-depth 8 --max-duration-seconds 120 --dry-run
python scripts/sync_tdn_snapshot.py snapshot --root-id 235312129 --cache-dir ./tdn-cache --max-depth 8 --checkpoint-every 25
```

Interrupções do snapshot podem ser retomadas com `--resume`. `--dry-run` e `--resume` são mutuamente exclusivos.

## Refresh

```bash
python scripts/sync_tdn_snapshot.py refresh --root-id 235312129 --cache-dir ./tdn-cache --max-depth 8
```

Apenas um escritor por raiz é permitido. Páginas inalteradas são copiadas para a nova geração sem baixar novamente o corpo. Páginas removidas recebem `status: removed`; páginas que virarem stubs recebem `status: filtered` e não mantêm conteúdo antigo como ativo.

Se uma execução for encerrada de forma abrupta e deixar `.snapshot.lock`, confirme primeiro que não existe outro escritor ativo antes de remover esse lock manualmente. O projeto não apaga locks antigos automaticamente.

## Export offline e chunks

```bash
python scripts/sync_tdn_snapshot.py export --root-id 235312129 --cache-dir ./tdn-cache --output-dir ./saida-local --offline
python scripts/process_tdn.py ./saida-local/tdn_pages.json ./saida-local/tdn_chunks.jsonl
```

O JSONL processado contém `id`, `source_url`, `title`, `chunk_index`, `total_chunks`, `modules`, `tables`, `parameters`, `routines`, `entry_points`, `target_audience` e `content`.

## Uso com Hermes Agent

O JSONL produzido por `process_tdn.py` mantém o contrato de contexto já usado com **Hermes Agent**. Entregue somente o arquivo revisado de chunks; não envie cache, HTML bruto, `.venv`, segredos ou materiais privados. Antes de usar o arquivo, valide que cada linha é JSON válido e contém `source_url`, `chunk_index`, `target_audience` e `content` não vazio.

## Uso com MCP

Depois de qualquer snapshot ou refresh, execute novamente o índice do projeto complementar `tdn-protheus-mcp`. O MCP deve recusar automaticamente um índice antigo com `POLICY_INDEX_STALE`.

## Verificação

```bash
python scripts/validate_skill.py .
```

Confira páginas ativas, filtradas, removidas, erros, URLs, data de coleta e amostras de tabelas/contratos antes de usar o dataset em decisões técnicas.

## Recursos

- `scripts/collect_tdn.py`: coleta direta simples.
- `scripts/locate_tdn_pages.py`: descoberta limitada por título.
- `scripts/sync_tdn_snapshot.py`: snapshot v2, refresh transacional, export offline e status.
- `scripts/process_tdn.py`: chunking interno, processamento JSONL e metadados.
- `scripts/validate_skill.py`: validação estrutural sem rede.
