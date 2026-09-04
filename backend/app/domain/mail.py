from __future__ import annotations

import re


def parse_recipients(raw: str) -> list[str]:
    if not raw:
        return []
    seen: list[str] = []
    found: set[str] = set()
    for part in re.split(r"[\s,;]+", raw.strip()):
        email = part.strip()
        key = email.lower()
        if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
            continue
        if key in found:
            continue
        found.add(key)
        seen.append(email)
    return seen
