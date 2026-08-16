# Code review P2

CONFIRMADO NO CÓDIGO: snapshots v2 publicam manifest atomicamente somente após mover staging para generation; refresh aborta staging em exceção; lock usa `O_EXCL`; leitor MCP compara fingerprint do manifest com o índice SQLite.

Correção aplicada: `FastMCPSettings.model_rebuild()` antes de criar o servidor resolve a referência forward `lifespan` com API pública Pydantic. Não há `filterwarnings` ou supressão.

Não foram encontrados P0/P1 novos no diff. Pontos mantidos como limites conhecidos: execução local não substitui a matriz GitHub hospedada; Dependency Review depende da habilitação da plataforma.
