"""List Catalog_Номенклатура property names from live $metadata. No secrets printed."""
from __future__ import annotations

import ssl
from base64 import b64encode
from pathlib import Path
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def load_env() -> dict[str, str]:
    out: dict[str, str] = {}
    p = ROOT / ".env"
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def fetch(url: str, user: str, password: str) -> bytes:
    token = b64encode(f"{user}:{password}".encode()).decode()
    req = Request(url, headers={"Authorization": f"Basic {token}", "Accept": "application/xml"})
    ctx = ssl._create_unverified_context()
    with urlopen(req, context=ctx, timeout=90) as resp:
        return resp.read()


def main() -> None:
    env = load_env()
    url = (env.get("ODATA_ASIL_URL") or "").rstrip("/") + "/$metadata"
    user = env.get("ODATA_ASIL_USER") or ""
    password = env.get("ODATA_ASIL_PASSWORD") or ""
    raw = fetch(url, user, password)
    root = ET.fromstring(raw)
    ns = {
        "edmx": "http://schemas.microsoft.com/ado/2007/06/edmx",
        "edm": "http://schemas.microsoft.com/ado/2009/11/edm",
        "edm2": "http://schemas.microsoft.com/ado/2008/09/edm",
        "edm3": "http://schemas.microsoft.com/ado/2006/04/edm",
    }
    names: list[str] = []
    for edm in ("edm", "edm2", "edm3"):
        for et in root.findall(f".//{{{ns[edm]}}}EntityType"):
            et_name = et.attrib.get("Name", "")
            if et_name not in {"Catalog_Номенклатура", "Номенклатура"}:
                continue
            for prop in list(et):
                n = prop.attrib.get("Name")
                if n:
                    names.append(n)
    out = ROOT / "docs" / "_nom_props.txt"
    lines = ["count " + str(len(set(names)))]
    for n in sorted(set(names)):
        lines.append(n)
    sets: list[str] = []
    for edm in ("edm", "edm2", "edm3"):
        for es in root.findall(f".//{{{ns[edm]}}}EntitySet"):
            n = es.attrib.get("Name") or ""
            if any(x in n for x in ("Вид", "Категор", "Модел", "Встав", "Штрих")):
                sets.append(n)
    lines.append("")
    lines.append("entity_sets:")
    for n in sorted(set(sets)):
        lines.append(n)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("wrote", out, "count", len(set(names)), "sets", len(set(sets)))


if __name__ == "__main__":
    main()
