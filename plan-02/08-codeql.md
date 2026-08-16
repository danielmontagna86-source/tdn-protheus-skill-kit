# CodeQL

O primeiro run comprovou que o repositório já possui CodeQL Default Setup habilitado na plataforma. GitHub recusa coexistência de análise avançada por `github/codeql-action` e Default Setup; o upload retornou: `CodeQL analyses from advanced configurations cannot be processed when the default setup is enabled`.

Classificação: `UPSTREAM/PLATFORM CONFIGURATION`. O workflow avançado foi removido para não manter uma CI sabidamente inválida. O gate CodeQL permanece a cargo do Default Setup GitHub, que já executa em PR/push e agenda. A interface disponível neste ciclo não expõe alertas do Default Setup; Critical/High permanecem `NÃO COMPROVADO` e impedem classificação PASS.
