"""Verify OData access and save $metadata."""
from __future__ import annotations

import base64
import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from _creds import ROOT, load_1c_creds

USER, PASSWORD = load_1c_creds()
BASE = "https://miamor.keenetic.pro:777/test3_asil/odata/standard.odata/"
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE


def get(path: str, accept: str = "application/json") -> tuple[int, bytes, str | None]:
    token = base64.b64encode(f"{USER}:{PASSWORD}".encode("utf-8")).decode("ascii")
    if "?" in path:
        entity, query = path.split("?", 1)
        encoded = urllib.parse.quote(entity, safe="/$()") + "?" + query
    else:
        encoded = urllib.parse.quote(path, safe="/$()")
    req = urllib.request.Request(BASE + encoded)
    req.add_header("Authorization", f"Basic {token}")
    req.add_header("Accept", accept)
    with urllib.request.urlopen(req, context=CTX, timeout=120) as resp:
        return resp.status, resp.read(), resp.headers.get("Content-Type")


def main() -> None:
    status, data, ctype = get("$metadata", "application/xml")
    out = ROOT / "docs" / "odata-metadata.xml"
    out.parent.mkdir(exist_ok=True)
    out.write_bytes(data)
    print(f"METADATA {status} len={len(data)} ctype={ctype} -> {out}")

    status, data, ctype = get("", "application/json")
    print(f"ROOT {status} ctype={ctype} len={len(data)}")

    meta_text = out.read_text(encoding="utf-8", errors="replace")
    needed = [
        "Номенклатура",
        "Контрагент",
        "РеализацияТоваровУслуг",
        "ВозвратТоваровОтПокупателя",
        "ЗаказКлиента",
        "ПоступлениеПродукцииИзПроизводства",
        "ПоступлениеТоваровУслуг",
    ]
    print("IN_METADATA:", [n for n in needed if n in meta_text])

    candidates = [
        "Catalog_Номенклатура",
        "Catalog_Контрагенты",
        "Document_РеализацияТоваровУслуг",
        "Document_ВозвратТоваровОтПокупателя",
        "Document_ЗаказКлиента",
        "Document_ПоступлениеПродукцииИзПроизводства",
        "Document_ПоступлениеТоваровУслуг",
    ]
    for ent in candidates:
        try:
            st, body, _ = get(f"{ent}?$top=1&$format=json")
            payload = json.loads(body.decode("utf-8"))
            rows = payload.get("value", [])
            keys = list(rows[0].keys())[:10] if rows else []
            print(f"OK {ent}: status={st} rows={len(rows)} keys={keys}")
        except urllib.error.HTTPError as exc:
            err = exc.read()[:200]
            print(f"FAIL {ent}: {exc.code} {err!r}")

    print("Credentials loaded from env/1c.txt (not written back).")


if __name__ == "__main__":
    main()
