from __future__ import annotations

from typing import Sequence

from app.constants import UploadStatus


def merge_upload_status(statuses: Sequence[str]) -> str:
    if not statuses:
        return UploadStatus.ERROR.value
    unique = {status for status in statuses if status}
    if unique == {UploadStatus.SUCCESS.value}:
        return UploadStatus.SUCCESS.value
    if unique == {UploadStatus.ERROR.value}:
        return UploadStatus.ERROR.value
    return UploadStatus.PARTIAL.value


def tag_error_message(
    message: str,
    *,
    file_name: str | None = None,
    row: int = 0,
    counterparty: str | None = None,
) -> str:
    text = (message or "").strip()
    if text.startswith("В файле"):
        return text
    parts: list[str] = []
    if file_name:
        parts.append(f"В файле «{file_name}»")
    if counterparty and counterparty not in text:
        parts.append(f"по {counterparty}")
    if row:
        parts.append(f"в строке {row}")
    if not parts:
        return text
    return f"{' '.join(parts)}: {text}"
