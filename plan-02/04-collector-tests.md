# Testes do coletor

CONFIRMADO PELO TESTE: 200, 401, 403, 404, 429, 500, 502, 503, timeout, `ConnectionError`, JSON inválido, paginação via `next` e offset, links externos/inválidos, redirect bloqueado, retry/backoff, deadline em retry/delay, HTML com tabela, remoção de script/style/footer/aside, Unicode, conteúdo curto, domínios permitido e não permitido e persistência JSON/JSONL.

O comportamento é dirigido por fakes de `requests.Session`; nenhum teste unitário consulta a TDN.
