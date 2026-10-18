"""Valida connectors/*.yaml. Sem rede: tudo aqui é leitura de arquivo.

Validates connectors/*.yaml, offline. Errors fail the run; warnings (re-verification age) do not,
unless --strict is given.

Regras / rules:
  1. esquema JSON (schema/connector.schema.json) e id == nome do arquivo;
  2. nenhum valor com cara de segredo — só NOMES de variáveis de ambiente;
  3. pacote stdio com versão FIXADA (nada de latest, ^, ~, *, intervalo);
  4. official: true exige evidência em fonte primária no domínio registrável do fornecedor
     (ou na org oficial dele no GitHub) — sufixo público (vercel.app, github.io…) reprova;
  5. categorias do vocabulário fechado (categories.yaml);
  6. checked_at com mais de 90 dias = aviso de reverificação (data no futuro = erro);
  7. conector OpenAPI usa o nome de chave que o Chimera deriva (CHIMERA_CONNECTOR_<NOME>_API_KEY);
  8. texto dirigido ao agente ou ao revisor ("ignore previous…") reprova.
"""

from __future__ import annotations

import datetime as dt
import os
import re
import sys
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlparse

import json

import jsonschema
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_catalog import CATEGORIES, ROOT, load_yaml  # noqa: E402

SCHEMA = ROOT / "schema" / "connector.schema.json"
REVERIFY_DAYS = 90

#: Formas de segredo reais. Um falso positivo aqui custa reescrever uma frase; um falso negativo
#: publica uma credencial num repositório público. A balança pende para reprovar.
SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("chave Stripe", re.compile(r"\b(sk|rk|pk)_(live|test)_[0-9A-Za-z]{8,}")),
    ("token GitHub", re.compile(r"\b(ghp|gho|ghu|ghs|ghr)_[0-9A-Za-z]{20,}|github_pat_[0-9A-Za-z_]{20,}")),
    ("token Slack", re.compile(r"\bxox[abposr]-[0-9A-Za-z-]{10,}")),
    ("chave AWS", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("chave Google", re.compile(r"\bAIza[0-9A-Za-z_-]{30,}")),
    ("chave Resend", re.compile(r"\bre_[0-9A-Za-z]{16,}")),
    ("token Hugging Face", re.compile(r"\bhf_[0-9A-Za-z]{20,}")),
    ("JWT", re.compile(r"\beyJ[0-9A-Za-z_-]{10,}\.[0-9A-Za-z_-]{10,}\.")),
    ("chave privada", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("Bearer com valor", re.compile(r"Bearer\s+[0-9A-Za-z._~+/-]{16,}")),
    ("credencial na URL", re.compile(r"https?://[^/\s:@]+:[^/\s@]+@")),
    ("segredo em query", re.compile(r"[?&](api[_-]?key|token|access_token|secret|password)=[^&\s{}<]{6,}", re.I)),
)
#: Sequência longa sem espaço que parece chave gerada (40+ hex ou 32+ base64-ish com dígitos).
LONG_OPAQUE = re.compile(r"(?<![0-9A-Za-z/._-])(?=[0-9A-Za-z_-]*\d)[0-9A-Za-z_-]{40,}(?![0-9A-Za-z/._-])")
PINNED_DIGEST = re.compile(r"@?sha256:[0-9a-f]{64}")
#: Campos onde um hash longo é esperado e fixa uma versão — não é segredo.
OPAQUE_ALLOWED_KEYS = {"digest"}

#: Frases dirigidas ao leitor-máquina. O PLANO manda o CI procurar esse tipo de texto.
INJECTION = re.compile(
    r"ignore (all |any )?(previous|prior|above) (instructions|messages)|disregard (the )?(previous|above)"
    r"|you are (now )?(an?|the) (ai|assistant|agent|model)|as an ai (assistant|model)|system prompt"
    r"|(reviewer|revisor|agent|agente)[,:]? (please )?(approve|aprove|merge|ignore)",
    re.I,
)

UNPINNED = re.compile(r"^(latest|next|main|master|\*|x)$|[\^~*<>|]|\s|\.x$", re.I)
VERSION_FORM = re.compile(r"^v?\d+(\.\d+){0,3}([.-][0-9A-Za-z.-]+)?$")
#: Sufixos públicos que NUNCA provam um fornecedor: qualquer um registra `algo.vercel.app`.
#: Lista curta e curada (PSL completa ficaria como dependência; ver CONTRIBUTING).
PUBLIC_SUFFIXES = {
    "vercel.app", "netlify.app", "github.io", "githubusercontent.com", "workers.dev", "pages.dev",
    "supabase.co", "herokuapp.com", "onrender.com", "fly.dev", "web.app", "firebaseapp.com",
    "azurewebsites.net", "cloudfront.net", "appspot.com", "glitch.me", "replit.app", "ngrok.io",
}
GITHUB_HOSTS = {"github.com", "www.github.com"}


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, where: str, msg: str) -> None:
        self.errors.append(f"ERRO   {where}: {msg}")

    def warn(self, where: str, msg: str) -> None:
        self.warnings.append(f"AVISO  {where}: {msg}")


def walk_strings(node: Any, path: str = "") -> Iterator[tuple[str, str, str]]:
    """(caminho, chave, valor) de toda string do documento, chaves incluídas."""
    if isinstance(node, dict):
        for key, value in node.items():
            sub = f"{path}.{key}" if path else str(key)
            yield sub, "<key>", str(key)
            yield from walk_strings(value, sub)
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from walk_strings(value, f"{path}[{i}]")
    elif isinstance(node, str):
        yield path, path.rsplit(".", 1)[-1], node


def host_in(host: str, domains: list[str]) -> bool:
    return any(host == d or host.endswith("." + d) for d in domains)


def check_secrets(where: str, data: dict[str, Any], rep: Report) -> None:
    for path, key, value in walk_strings(data):
        for label, pat in SECRET_PATTERNS:
            if pat.search(value):
                rep.error(where, f"{path}: valor parece {label} — o repositório guarda só NOMES de variáveis")
        # Um digest sha256 fixa uma imagem; é o oposto de segredo, então sai da varredura.
        scrubbed = PINNED_DIGEST.sub("", value)
        if key not in OPAQUE_ALLOWED_KEYS and LONG_OPAQUE.search(scrubbed):
            rep.error(where, f"{path}: sequência longa e opaca parece segredo ({value[:12]}…)")
        if key != "<key>" and INJECTION.search(value):
            rep.error(where, f"{path}: texto dirigido a agente/revisor não pode entrar no catálogo")
    env_fixed = (data.get("stdio") or {}).get("env_fixed") or {}
    secretish = re.compile(r"(TOKEN|SECRET|PASSWORD|API_KEY|PRIVATE|CREDENTIAL)", re.I)
    for name in env_fixed:
        if secretish.search(name):
            rep.error(where, f"stdio.env_fixed.{name}: variável de segredo não pode ter valor fixo; liste o nome em auth.env")


def check_pinned(where: str, data: dict[str, Any], rep: Report) -> None:
    stdio = data.get("stdio")
    if not stdio:
        return
    version = str(stdio.get("version", ""))
    if UNPINNED.search(version) or not VERSION_FORM.match(version):
        rep.error(where, f"stdio.version {version!r} não é uma versão fixada")
    args = [str(a) for a in stdio.get("args", [])]
    for a in args:
        if a.endswith("@latest") or "@latest " in a or a.endswith("@next"):
            rep.error(where, f"stdio.args contém {a!r}: fixe a versão")
    runner, package = stdio.get("runner"), str(stdio.get("package", ""))
    expected = {
        "npx": f"{package}@{version}",
        "uvx": f"{package}=={version}",
        "docker": f"{package}:{version}" + (f"@{stdio['digest']}" if stdio.get("digest") else ""),
    }.get(str(runner))
    if expected and not any(expected in a for a in args):
        rep.error(where, f"stdio.args não executa a versão fixada (esperado {expected!r} num argumento)")


def check_official(where: str, data: dict[str, Any], rep: Report) -> None:
    ev = data["evidence"]
    domains = [d.lower() for d in ev.get("vendor_domains", [])]
    for d in domains:
        if d in PUBLIC_SUFFIXES:
            rep.error(where, f"evidence.vendor_domains: {d!r} é sufixo público e não prova fornecedor")
    if not data["official"]:
        return
    if not domains:
        rep.error(where, "official: true exige evidence.vendor_domains")
    url = urlparse(ev["url"])
    host = (url.hostname or "").lower()
    if any(host == s or host.endswith("." + s) for s in PUBLIC_SUFFIXES):
        rep.error(where, f"evidence.url em sufixo público ({host}) não prova o fornecedor")
    if ev["method"] == "vendor-repo":
        orgs = [o.lower() for o in ev.get("vendor_github_orgs", [])]
        org = url.path.strip("/").split("/")[0].lower() if host in GITHUB_HOSTS else ""
        if not orgs or org not in orgs:
            rep.error(where, "evidence vendor-repo exige URL em github.com/<org> listada em vendor_github_orgs")
    elif ev["method"] == "vendor-docs":
        if not host_in(host, domains):
            rep.error(where, f"evidence.url ({host}) fora dos domínios do fornecedor {domains}")
    elif ev["method"] == "registry-domain":
        if host != "registry.modelcontextprotocol.io":
            rep.error(where, "evidence registry-domain exige URL do registro oficial")


def check_dates(where: str, data: dict[str, Any], today: dt.date, rep: Report) -> None:
    dates = [("evidence.checked_at", data["evidence"]["checked_at"])]
    if data.get("stars"):
        dates.append(("stars.checked_at", data["stars"]["checked_at"]))
    for label, raw in dates:
        try:
            day = dt.date.fromisoformat(raw)
        except ValueError:
            rep.error(where, f"{label} {raw!r} não é data")
            continue
        if day > today:
            rep.error(where, f"{label} {raw} está no futuro")
        elif label == "evidence.checked_at" and (today - day).days > REVERIFY_DAYS:
            badge = " — o selo 'Oficial' sai da tela até reverificar" if data["official"] else ""
            rep.warn(where, f"verificado há {(today - day).days} dias (> {REVERIFY_DAYS}){badge}")


def check_semantics(where: str, data: dict[str, Any], cats: set[str], rep: Report) -> None:
    c = data["categories"]
    for cat in [c["primary"], *c["secondary"]]:
        if cat not in cats:
            rep.error(where, f"categoria {cat!r} não está em categories.yaml")
    if c["primary"] in c["secondary"]:
        rep.error(where, "categoria principal repetida nas secundárias")
    cap = data["capability"]
    if data["default_mode"] == "read_only" and not cap["read"]:
        rep.error(where, "default_mode read_only sem capability.read")
    if data["kind"] == "openapi":
        api = data["openapi"]
        expected = f"CHIMERA_CONNECTOR_{api['connector_name'].upper()}_API_KEY"
        if data["auth"]["method"] == "api_key" and data["auth"]["env"] != [expected]:
            rep.error(where, f"auth.env de conector OpenAPI deve ser [{expected}] (o nome que o Chimera deriva)")
    if data["auth"]["method"] == "none" and data["auth"]["env"]:
        rep.error(where, "auth.method none com variáveis em auth.env")
    if data["license"] is not None and data.get("stars") is None and data["transport"] == "stdio":
        rep.warn(where, "servidor aberto sem estrelas registradas")


def main(argv: list[str]) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    today = dt.date.fromisoformat(os.environ["CHECK_TODAY"]) if os.environ.get("CHECK_TODAY") else dt.date.today()
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    cats = {c["id"] for c in load_yaml(CATEGORIES)["categories"]}
    rep = Report()
    seen: set[str] = set()
    items: list[tuple[Path, Any]] = []
    for path in sorted((ROOT / "connectors").glob("*.yaml")):
        try:
            items.append((path, load_yaml(path)))
        except yaml.YAMLError as exc:
            rep.error(path.name, f"YAML inválido: {str(exc).splitlines()[0]}")
    if not items and not rep.errors:
        rep.error("connectors/", "nenhum conector")
    for path, data in items:
        where = path.name
        if not isinstance(data, dict):
            rep.error(where, "documento não é um mapa YAML")
            continue
        schema_errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
        for err in schema_errors:
            loc = "/".join(str(p) for p in err.path) or "(raiz)"
            rep.error(where, f"esquema: {loc}: {err.message}")
        # As regras abaixo leem campos obrigatórios; um documento fora do esquema já reprovou.
        check_secrets(where, data, rep)
        if schema_errors:
            continue
        if data["id"] != path.stem:
            rep.error(where, f"id {data['id']!r} difere do nome do arquivo")
        if data["id"] in seen:
            rep.error(where, "id duplicado")
        seen.add(data["id"])
        check_pinned(where, data, rep)
        check_official(where, data, rep)
        check_dates(where, data, today, rep)
        check_semantics(where, data, cats, rep)
    for line in rep.errors + rep.warnings:
        print(line)
    print(f"{len(items)} conectores · {len(rep.errors)} erro(s) · {len(rep.warnings)} aviso(s)")
    if rep.errors or ("--strict" in argv and rep.warnings):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
