# Troubleshooting — Skill Kit

| Sintoma | Ação |
|---|---|
| Dry-run termina com `complete: false` | Veja `stop_reason` e reduza a raiz/profundidade ou ajuste limites conscientemente. |
| Snapshot interrompido | Preserve `run_state.json` e use `--resume` somente para uma execução compatível. |
| `manifesto inexistente` | Execute um snapshot completo antes de `refresh`, `export` ou `status`. |
| Resultado do localizador vazio | Confirme `complete`; uma descoberta limitada não prova ausência documental. |
| Instalação já existe | Revise a instalação atual; use `--force` somente quando quiser substituição explícita. |
| Export offline falha | Confirme o mesmo `root-id` e `cache-dir` usados na coleta. |
