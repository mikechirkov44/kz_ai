"""Diagnose 1C OData authentication."""
from __future__ import annotations

import base64
import ssl
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
cred = (ROOT / "1c.txt").read_text(encoding="utf-8").strip()
idx = cred.lower().index("пароль")
user = cred[:idx].replace("Пользователь", "").replace("пользователь", "").strip()
password = cred[idx + len("пароль") :].strip()

BASE = "https://miamor.keenetic.pro:777/test3_asil/odata/standard.odata/"
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

USERS = [
    user,
    user.rstrip("."),
    user.replace(" ", ""),
    "Куковеров В.",
    "Куковеров в.",
    "куковеров в",
    "КуковеровВ",
]


def probe(u: str, enc: str) -> None:
    token = base64.b64encode(f"{u}:{password}".encode(enc)).decode("ascii")
    req = urllib.request.Request(BASE)
    req.add_header("Authorization", f"Basic {token}")
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, context=CTX, timeout=30) as resp:
            print(f"OK user={u!r} enc={enc} status={resp.status}")
            print("  headers:", dict(resp.headers))
            print("  body:", resp.read(200))
    except urllib.error.HTTPError as exc:
        print(f"FAIL user={u!r} enc={enc} status={exc.code}")
        print("  www-authenticate:", exc.headers.get("WWW-Authenticate"))
        print("  server:", exc.headers.get("Server"))
        title = exc.read(400)
        if b"401." in title:
            # extract 401.x
            import re

            m = re.search(rb"401\.\d+", title)
            print("  iis:", m.group(0).decode() if m else title[:120])
        else:
            print("  body:", title[:160])


def main() -> None:
    print("parsed user:", repr(user), "pwd_len:", len(password))
    # no auth
    req = urllib.request.Request(BASE)
    try:
        urllib.request.urlopen(req, context=CTX, timeout=20)
    except urllib.error.HTTPError as exc:
        print("NOAUTH", exc.code, "WWW-Authenticate:", exc.headers.get("WWW-Authenticate"))

    for u in USERS:
        for enc in ("utf-8", "cp1251"):
            probe(u, enc)


if __name__ == "__main__":
    main()
