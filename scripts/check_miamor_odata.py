"""Live connectivity check for second 1C base (miamor). Does not print secrets."""
from __future__ import annotations

import ssl
from base64 import b64encode
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def load_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = value.strip().strip('"').strip("'")
    return out


def main() -> None:
    env = load_env(ROOT / ".env")
    url = env.get("ODATA_MIAMOR_URL") or "https://miamor.keenetic.pro:777/test4_miamor/odata/standard.odata/"
    user = env.get("ODATA_MIAMOR_USER") or env.get("ODATA_ASIL_USER") or ""
    password = env.get("ODATA_MIAMOR_PASSWORD") or env.get("ODATA_ASIL_PASSWORD") or ""
    if not user or not password:
        print("miamor_skip: no credentials in .env")
        return

    meta = url.rstrip("/") + "/$metadata"
    token = b64encode(f"{user}:{password}".encode()).decode()
    req = Request(meta, headers={"Authorization": f"Basic {token}", "Accept": "application/xml"})
    ctx = ssl._create_unverified_context()
    try:
        with urlopen(req, context=ctx, timeout=45) as resp:
            chunk = resp.read(120)
            print(f"miamor_ok status={resp.status} content_type={resp.headers.get('Content-Type','')} sample_len={len(chunk)}")
    except HTTPError as exc:
        print(f"miamor_http status={exc.code} reason={exc.reason}")
    except URLError as exc:
        print(f"miamor_network error={exc.reason}")


if __name__ == "__main__":
    main()
