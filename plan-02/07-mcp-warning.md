# MCP — IncompleteFieldDefinitionWarning

REPRODUZIDO: Python 3.12, MCP 1.29.0 (última estável da linha 1.x), pydantic 2.13.4 e pydantic-settings 2.15.0. O aviso vinha de `pydantic_settings.sources.utils` ao materializar `mcp.server.fastmcp.server.Settings`; o campo era `lifespan` com forward reference genérica.

CONFIRMADO NO CÓDIGO: `Settings.model_rebuild()` elimina o aviso antes de `BaseSettings` consultar sources. Teste stdio MCP continua PASS sem warning. Esta é uma correção compatível na linha 1.x, não uma migração para MCP 2.

Python 3.11 não estava disponível neste executor local; a matriz GitHub 3.11/3.12 é o verificador final.
