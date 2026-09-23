"""Manager display and ownership from 1C names (not app user assignment)."""

from __future__ import annotations

from typing import Any, Optional

from app.odata.mapping import manager_name_from_properties


def normalize_manager_name(value: Optional[str]) -> str:
    return " ".join(str(value or "").split()).casefold()


def display_manager_name(
    counterparty: Any,
    *,
    assigned_name: Optional[str] = None,
) -> Optional[str]:
    """Prefer 1C name, then extra properties, then legacy assigned user."""
    for candidate in (
        getattr(counterparty, "onec_manager_name", None),
        manager_name_from_properties(getattr(counterparty, "extra_properties", None)),
        assigned_name,
    ):
        text = str(candidate or "").strip()
        if text:
            return text
    return None


def user_manager_name(user: Any) -> str:
    return normalize_manager_name(getattr(user, "full_name", None) or "")


def counterparty_belongs_to_manager(counterparty: Any, user: Any) -> bool:
    """True when 1C manager name matches the user's FIO, or legacy manager_id matches."""
    if getattr(counterparty, "manager_id", None) is not None and counterparty.manager_id == getattr(user, "id", None):
        return True
    label = user_manager_name(user)
    if not label:
        return False
    return normalize_manager_name(display_manager_name(counterparty)) == label
