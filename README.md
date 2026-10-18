# chimera-connectors

*[English below](#english)*

Catálogo curado de **conectores** para o [Chimera](https://github.com/brcampidelli/chimera-agent):
servidores MCP (hospedados ou locais) e APIs com especificação OpenAPI. Um arquivo YAML por conector
em `connectors/`; o CI gera `dist/catalog.json`, que é o que o app lê.

**O catálogo só preenche o formulário.** Adicionar um conector continua sendo decisão do dono dentro
do Chimera: nada é instalado ligado, e o app mostra o que o conector pode fazer antes de pedir
qualquer credencial.

## Regras

1. **Nenhum segredo, nunca.** O repositório guarda só **nomes** de variáveis de ambiente
   (`auth.env`). Nenhum valor, nem de exemplo realista. O `scripts/check.py` reprova qualquer coisa
   com cara de chave, token ou credencial em URL.
2. **Selo "Oficial do fornecedor" só com prova.** `official: true` exige uma fonte primária —
   documentação no domínio registrável do fornecedor, ou repositório na organização oficial dele no
   GitHub — registrada em `evidence.url` com a data em `evidence.checked_at`. Sufixos públicos
   (`algo.vercel.app`, `algo.github.io`…) nunca provam fornecedor. Diretórios e blogs não contam.
   O selo é do Chimera ("verificado pelo Chimera em AAAA-MM-DD"), não endosso do fornecedor.
3. **Reverificar a cada 90 dias.** Com `checked_at` mais velho que isso, o CI avisa e o app esconde
   o selo até alguém reler a fonte.
4. **Versão fixada.** Servidor local roda a versão lida (`stdio.version`, repetida nos `args`);
   imagem Docker com tag **e** digest. `@latest`, `^`, `~` e intervalos reprovam.
5. **Capacidade honesta.** `capability` diz o que o servidor consegue fazer no pior caso (ler,
   escrever, executar código/infra, mexer com dinheiro — mover dinheiro, comprar ou gerar cobrança
   por ação). `default_mode` é o modo mais restrito **que o fornecedor impõe** e é o que o catálogo
   instala: `read_only` (imposto pelo servidor), `scoped` (estreitado por escopo, skill ou permissão
   da chave, sem garantia de só leitura) ou `full` (o fornecedor não oferece estreitamento).
6. **Popularidade só com dado público.** Estrelas do GitHub com a data da leitura, quando o código é
   aberto. Nenhuma contagem de instalações.
7. **Logos.** Só de kit de marca oficial cujos termos permitam o uso; caso contrário, monograma
   neutro. O repositório guarda a **decisão** (`logo.decision`), não arquivos de logo de terceiros.
8. **Login (DCR).** `auth.dcr_supported` registra se o servidor de autorização anuncia registro
   dinâmico de cliente (lido na descoberta OAuth do próprio endpoint, anotada em
   `evidence.oauth_probe`); `auth.client_restriction` diz se o fornecedor só aceita clientes
   aprovados (`allowlist`), exige um app do próprio usuário (`own_app`) ou um tenant corporativo
   (`tenant`).

Fora do catálogo, de propósito: automação não oficial de WhatsApp (whatsapp-web.js e similares, que
o próprio projeto avisa que pode levar a banimento), proxies que reaproveitam assinaturas de
terceiros, e eToro/MT5 (o Chimera opera esses por scripts determinísticos).

## Estrutura

```
connectors/<id>.yaml        um conector por arquivo
schema/connector.schema.json
categories.yaml             27 categorias — cópia exata do arquivo canônico comum a plugins, skills e conectores
scripts/check.py            validação (esquema, segredos, versões, evidência, categorias, idade)
scripts/build_catalog.py    gera dist/catalog.json (determinístico, ordenado)
dist/catalog.json           gerado — não editar à mão
```

## Pendente

- TODO(M3): assinar `dist/catalog.json`. Até lá, o app fixa este repositório por commit (sha).

## Rodar localmente

```bash
python -m pip install --require-hashes --no-deps -r requirements.txt
python scripts/check.py
python scripts/build_catalog.py          # e commitar dist/catalog.json junto
```

## Licença

O conteúdo deste repositório é Apache-2.0 (ver `LICENSE`). Nomes e marcas citados pertencem aos
seus donos; o catálogo aponta para servidores e especificações de terceiros, não os redistribui.

---

## English

A curated catalog of **connectors** for [Chimera](https://github.com/brcampidelli/chimera-agent):
MCP servers (hosted or local) and APIs described by an OpenAPI spec. One YAML file per connector in
`connectors/`; CI builds `dist/catalog.json`, which is what the app reads.

**The catalog only pre-fills the form.** Adding a connector remains the owner's decision inside
Chimera: nothing is installed enabled, and the app shows what a connector can do before it asks for
any credential.

### Rules

1. **Never a secret.** Only environment variable **names** (`auth.env`). `scripts/check.py` rejects
   anything that looks like a key, a token or a credential in a URL.
2. **"Vendor official" badge only with proof** from a primary source on the vendor's registrable
   domain or the vendor's official GitHub org, recorded in `evidence.url` with `evidence.checked_at`.
   Public suffixes (`*.vercel.app`, `*.github.io`, …) never prove a vendor. The badge is Chimera's,
   not an endorsement by the vendor.
3. **Re-verified every 90 days**; older entries produce a CI warning and lose the badge in the app.
4. **Pinned versions** for local servers (and tag + digest for Docker images). No `@latest`.
5. **Honest capability**: `capability` is the worst case (read, write, executes code/infra, money —
   moves money, purchases, or bills per action); `default_mode` is the most restrictive mode the
   vendor enforces, and it is what gets installed.
6. **Popularity**: GitHub stars with the date they were read, nothing else. No install counts.
7. **Logos**: official brand kit only when its terms allow it, otherwise a neutral monogram. The
   repository stores the decision, not third-party logo files.
8. **Sign-in**: `auth.dcr_supported` records whether the authorization server advertises dynamic
   client registration (read from the endpoint's own OAuth discovery); `auth.client_restriction`
   says whether the vendor only accepts approved clients, requires the user's own app, or a
   corporate tenant.

TODO(M3): sign `dist/catalog.json`; until then the app pins this repository by commit.

Content is licensed Apache-2.0. Names and trademarks belong to their owners; the catalog points to
third-party servers and specs and does not redistribute them.
