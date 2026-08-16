# Testes de snapshot/sync

CONFIRMADO PELO TESTE: snapshot novo, v1, v2, migração v1→v2, unchanged, changed, removida, filtrada, reativada, múltiplas páginas, staging failure, deadline global, resume na mesma generation, resume inválido, partial state, manifest/page directory inválidos, lock/contenção, collision de generation, rollback, export/status v1 e v2.

Invariantes comprovados: manifest ativo e bytes ativos permanecem inalterados em falha de refresh; staging não fica ativo; lock rejeita segundo writer; resume usa a mesma staging generation; nova execução recusa state parcial silencioso.
