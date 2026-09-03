"""Load 1C OData credentials from env or local 1c.txt (never commit secrets)."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_1c_creds() -> tuple[str, str]:
    user = os.getenv("ODATA_ASIL_USER", "").strip()
    password = os.getenv("ODATA_ASIL_PASSWORD", "").strip()
    if user and password:
        return user, password

    cred_file = ROOT / "1c.txt"
    if not cred_file.exists():
        raise SystemExit("Set ODATA_ASIL_USER/ODATA_ASIL_PASSWORD or create 1c.txt")

    text = cred_file.read_text(encoding="utf-8").strip()
    lower = text.lower()
    if "пароль" not in lower:
        raise SystemExit(f"Cannot parse {cred_file}")
    idx = lower.index("пароль")
    user_part = text[:idx].replace("Пользователь", "").replace("пользователь", "").strip()
    password = text[idx + len("пароль") :].strip()
    if not user_part or not password:
        raise SystemExit(f"Empty credentials in {cred_file}")
    return user_part, password
