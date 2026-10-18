"""Gera dist/catalog.json a partir de connectors/*.yaml — determinístico e ordenado.

Builds dist/catalog.json from connectors/*.yaml. Deterministic: entries sorted by id, keys sorted,
no timestamp. The same YAML always produces the same bytes, so CI can fail on a stale file.

    python scripts/build_catalog.py           # escreve / writes dist/catalog.json
    python scripts/build_catalog.py --check   # falha se o arquivo estiver desatualizado / fails if stale
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONNECTORS = ROOT / "connectors"
CATEGORIES = ROOT / "categories.yaml"
OUT = ROOT / "dist" / "catalog.json"
#: Sobe quando o formato do catalog.json muda de um jeito que o app precisa saber.
CATALOG_FORMAT = 1


def load_yaml(path: Path) -> Any:
    # safe_load: o YAML é dado de terceiros num PR; nunca construir objetos Python a partir dele.
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_connectors() -> list[tuple[Path, dict[str, Any]]]:
    return [(p, load_yaml(p)) for p in sorted(CONNECTORS.glob("*.yaml"))]


def render() -> str:
    entries = sorted((data for _, data in load_connectors()), key=lambda d: d["id"])
    # Arquivo canônico compartilhado pelos três repositórios: {categories: [{id, pt}, …]}.
    categories = load_yaml(CATEGORIES)["categories"]
    body = {
        "format": CATALOG_FORMAT,
        "categories": categories,
        "connectors": entries,
    }
    return json.dumps(body, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main(argv: list[str]) -> int:
    text = render()
    if "--check" in argv:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != text:
            print("dist/catalog.json está desatualizado: rode `python scripts/build_catalog.py`.")
            print("dist/catalog.json is stale: run `python scripts/build_catalog.py`.")
            return 1
        print(f"dist/catalog.json em dia ({text.count(chr(10))} linhas).")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    # newline="\n": o mesmo arquivo em Windows e Linux, senão o --check acusa diferença falsa.
    with OUT.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print(f"escrito {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
