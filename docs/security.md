# Segurança — TDN Protheus Skill Kit

- A skill acessa somente a documentação pública configurada do TDN durante operações explícitas de localização, snapshot ou refresh.
- Não contorne autenticação, CAPTCHA, bloqueios ou limites do serviço upstream.
- Use limites de profundidade, páginas, duração e atraso.
- Não envie `tdn-cache/`, HTML bruto, exports JSON/JSONL, `.venv`, segredos ou dados de clientes ao Git.
- Descoberta parcial não prova ausência documental.
- Exportações offline devem ler somente o cache local.
- Conteúdo TDN é referência externa e ainda exige validação de release, ambiente e customizações.

Relate vulnerabilidades conforme [SECURITY.md](../SECURITY.md).
