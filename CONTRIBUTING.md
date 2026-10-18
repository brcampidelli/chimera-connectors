# Contribuindo / Contributing

*PT-BR primeiro; English summary at the end.*

## Propor um conector

1. Crie `connectors/<id>.yaml` seguindo `schema/connector.schema.json` (copie um vizinho do mesmo
   tipo: `linear.yaml` para HTTP, `playwright.yaml` para stdio, `resend.yaml` para OpenAPI).
2. **Fonte primária.** `evidence.url` precisa ser a página de documentação do fornecedor, no
   domínio registrável dele, que cita o endpoint ou o pacote — ou o repositório na organização
   oficial dele no GitHub. Liste esses domínios em `evidence.vendor_domains` e as orgs em
   `evidence.vendor_github_orgs`. Não vale: Smithery, Glama, PulseMCP, blogs, ou o registro oficial
   sob um namespace que não seja o domínio do fornecedor (por exemplo `app.vercel.*`, que pertence a
   quem tem `algo.vercel.app`, não à Vercel). Sem isso, `official: false` e a nota diz
   "não verificado".
3. **Descoberta OAuth.** Para endpoint HTTP, leia o `WWW-Authenticate` do `401`, o
   `/.well-known/oauth-protected-resource` e os metadados do servidor de autorização, e registre em
   `evidence.oauth_probe` se há `registration_endpoint` (DCR). Só leitura: nunca registre um cliente
   de verdade para testar.
4. **Versão.** Para stdio, a versão que você **leu** (README e, de preferência, o pacote
   desempacotado), repetida nos `args`. Atualizar a versão exige reler.
5. **Capacidade e modo padrão.** Marque o pior caso em `capability` e escolha em `default_mode` o
   modo mais restrito que o **servidor impõe** (endpoint `/readonly`, `read_only=true`, skill de
   leitura, variável de só leitura). Uma dica de "somente leitura" que o cliente pode ignorar não
   conta como `read_only`.
6. **Segredos.** Só nomes em `auth.env`. Para conector OpenAPI, o nome é o que o Chimera deriva:
   `CHIMERA_CONNECTOR_<CONNECTOR_NAME>_API_KEY`.
7. **Logo.** `monogram` salvo quando o kit de marca oficial permite o uso, com o link dos termos em
   `logo.decision`. Não comite arquivos de logo de terceiros.
8. **Estrelas.** Só para código aberto no GitHub, com `stars.checked_at`.
9. Rode `python scripts/check.py` e `python scripts/build_catalog.py`, e comite o
   `dist/catalog.json` gerado no mesmo PR.

O texto que vem de terceiros (READMEs, licenças, descrições) é dado, nunca instrução. O CI reprova
frases dirigidas ao agente ou ao revisor. Revisão humana antes de qualquer merge; o dono do
repositório decide.

## Reverificação

A cada 90 dias, releia a fonte de cada conector oficial, atualize `evidence.checked_at` (e as
estrelas) e corrija o que mudou. Endpoint que responde 404 ou pacote despublicado sai no mesmo dia.

## Limites conhecidos do `check.py`

- A lista de sufixos públicos é curta e curada, não a Public Suffix List completa. Na dúvida sobre
  um domínio, confira em <https://publicsuffix.org/list/>.
- A detecção de segredos é por padrão; ela complementa, não substitui, a revisão humana e um
  scanner como o gitleaks.

---

## English summary

One YAML per connector, validated against the schema. `official: true` requires a primary source on
the vendor's registrable domain or its official GitHub org, dated; public suffixes and third-party
directories never count. Record the OAuth discovery result (DCR or not) read-only. Pin the version
you actually read. Declare worst-case capability and install the narrowest mode the server itself
enforces. Environment variable names only — never values. Monogram unless the official brand kit's
terms allow the logo. Run `scripts/check.py` and `scripts/build_catalog.py` and commit
`dist/catalog.json` in the same PR. Third-party text is data, never instructions.
