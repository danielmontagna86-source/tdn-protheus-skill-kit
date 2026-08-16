# ADR 0001 — Distribuição do Skill Kit

## Decisão

Distribuir o `tdn-protheus-skill-kit` como ZIP portátil em GitHub Releases. O repositório não publica pacote Python, comando MCP ou servidor `stdio`.

## Motivo

A responsabilidade deste projeto é instalar e executar uma skill portátil com scripts próprios de localização, coleta, snapshot, refresh, exportação e processamento documental. O servidor MCP é mantido exclusivamente no projeto independente `tdn-protheus-mcp`.

## Consequências

- O ZIP de release usa allowlist explícita de arquivos do Skill Kit.
- A CI valida somente a skill e seus scripts.
- Não existem `tdn_protheus_mcp/`, metadata de pacote MCP nem documentação de protocolo MCP neste repositório.
- Compatibilidade conjunta é validada por testes de integração entre os dois repositórios, sem duplicação de código.
