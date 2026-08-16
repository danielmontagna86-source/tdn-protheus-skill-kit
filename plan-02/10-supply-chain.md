# Supply chain

Skill: `pip-audit -r requirements.txt` PASS; ZIP, SBOM CycloneDX e SHA256SUMS PASS. A CI/release instala `requirements-ci.txt` com `setuptools>=83`.

MCP: `pip-audit` PASS; `build`, wheel, sdist, Twine, SBOM e SHA256SUMS PASS. `pyproject.toml` já exige `setuptools>=83`; teste de metadata protege esta regressão ligada ao caso PYSEC-2026-3447.

Nenhuma auditoria foi desativada. Pacotes de distribuição não incluem cache TDN ou dados locais.
