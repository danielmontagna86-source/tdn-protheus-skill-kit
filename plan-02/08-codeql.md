# CodeQL

O primeiro run comprovou que o repositório já possui CodeQL Default Setup habilitado na plataforma. GitHub recusa coexistência de análise avançada por `github/codeql-action` e Default Setup; o upload retornou: `CodeQL analyses from advanced configurations cannot be processed when the default setup is enabled`.

Classificação: `UPSTREAM/PLATFORM CONFIGURATION` para a escolha entre Default Setup e configuração avançada, não para o resultado do gate. O workflow avançado foi removido para não manter uma CI sabidamente inválida. Para tornar o estado verificável, foi adicionado `CodeQL Alert Gate`: em PR, push para main e agenda semanal, com somente `contents: read` e `security-events: read`, ele consulta a API oficial e falha se existir alerta aberto High ou Critical.

CONFIRMADO PELO TESTE HOSPEDADO: Skill run `31979565651` e MCP run `31979564758` concluíram `success`; portanto Critical = 0 e High = 0 no momento das execuções. RESULTADO: PASS.
