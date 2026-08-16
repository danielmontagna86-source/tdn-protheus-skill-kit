# Teste prático 3 — stale index

Fixture controlada: generation A (`generation-A`, fingerprint `67094b3c23f08e94bdb4ce5ed28b0865abc93d8a1339cdba87ccee2cc94d36bb`) foi indexada e retornou `10:0`.

Após publicar atomicamente generation B (`generation-B`, fingerprint `06c3410e7b0147fd8c6255be1c69ab9cba6bd46702bc2f6037cfc85cd436a9da`) sem reindexar, search recusou com `POLICY_INDEX_STALE`. Após reindexar, o fingerprint foi B e a busca retornou `20:0`.
