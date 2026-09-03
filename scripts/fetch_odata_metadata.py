"""Fetch OData $metadata from 1C test base."""
from __future__ import annotations

import base64
import ssl
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CREDS = ROOT / "1c.txt"
OUT_DIR = ROOT / "docs"
OUT_FILE = OUT_DIR / "odata-metadata.xml"
BASE = "https://miamor.keenetic.pro:777/test3_asil/odata/standard.odata/$metadata"


def load_creds() -> tuple[str, str]:
    text = CREDS.read_text(encoding="utf-8").strip()
    # Format: "Пользователь <name> пароль <pass>"
    lower = text.lower()
    if "пароль" in lower:
        idx = lower.index("пароль")
        user_part = text[:idx]
        password = text[idx + len("пароль") :].strip()
        user = user_part.replace("Пользователь", "").replace("пользователь", "").strip()
        return user, password
    raise ValueError(f"Cannot parse credentials from {CREDS}")


def main() -> None:
    user, password = load_creds()
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    req = urllib.request.Request(BASE)
    token = base64.b64encode(f"{user}:{password}".encode("utf-8")).decode("ascii")
    req.add_header("Authorization", f"Basic {token}")
    req.add_header("Accept", "application/xml")

    try:
        with urllib.request.urlopen(req, context=ctx, timeout=120) as resp:
            data = resp.read()
            print(f"STATUS {resp.status} LEN {len(data)}")
    except urllib.error.HTTPError as exc:
        body = exc.read()
        print(f"HTTP {exc.code}: {body[:800]!r}")
        raise

    OUT_DIR.mkdir(exist_ok=True)
    OUT_FILE.write_bytes(data)
    print(f"SAVED {OUT_FILE}")
    text = data.decode("utf-8", errors="replace")
    print(text[:3000])


if __name__ == "__main__":
    main()
