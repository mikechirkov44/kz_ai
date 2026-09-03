"""Probe 1C endpoints and auth."""
from __future__ import annotations

import base64
import ssl
import urllib.error
import urllib.request

from _creds import load_1c_creds

USER, PASSWORD = load_1c_creds()
PATHS = [
    "https://miamor.keenetic.pro:777/test3_asil/",
    "https://miamor.keenetic.pro:777/test3_asil/ru/",
    "https://miamor.keenetic.pro:777/test3_asil/odata/standard.odata/",
    "https://miamor.keenetic.pro:777/test3_asil/odata/standard.odata/$metadata",
]


def main() -> None:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    token = base64.b64encode(f"{USER}:{PASSWORD}".encode("utf-8")).decode("ascii")

    for url in PATHS:
        for with_auth in (False, True):
            req = urllib.request.Request(url)
            if with_auth:
                req.add_header("Authorization", f"Basic {token}")
            try:
                with urllib.request.urlopen(req, context=ctx, timeout=20) as resp:
                    body = resp.read(120)
                    print("OK", with_auth, url, resp.status, body[:60])
            except urllib.error.HTTPError as exc:
                print("HTTP", with_auth, url, exc.code)
            except Exception as exc:  # noqa: BLE001
                print("ERR", with_auth, url, type(exc).__name__, exc)


if __name__ == "__main__":
    main()
