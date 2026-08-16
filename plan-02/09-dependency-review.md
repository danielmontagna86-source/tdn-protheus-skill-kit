# Dependency Review

Adicionado aos dois projetos em `pull_request` para main usando `actions/dependency-review-action@v5.0.0` por SHA, com `fail-on-severity: moderate`.

RESULTADO: PASS nos dois projetos. O MCP inicialmente retornou `BLOCKED_BY_PLATFORM` porque o Dependency Graph estava desabilitado. Após habilitação na configuração do repositório, a reexecução oficial do run `31978377887` (run number 2) concluiu `success`. Não há downgrade configurado.
