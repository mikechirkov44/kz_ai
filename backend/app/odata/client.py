from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Iterator, Optional
from urllib.parse import quote, urljoin

import httpx

from app.config import settings
from app.constants import SOURCE_ASIL, SOURCE_MIAMOR

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ODataSource:
    source_id: str
    base_url: str
    username: str
    password: str
    verify_ssl: bool = False

    @property
    def enabled(self) -> bool:
        return bool(self.base_url and self.username)


def configured_sources() -> list[ODataSource]:
    sources = [
        ODataSource(
            source_id=SOURCE_ASIL,
            base_url=settings.odata_asil_url,
            username=settings.odata_asil_user,
            password=settings.odata_asil_password,
            verify_ssl=settings.odata_asil_verify_ssl,
        ),
        ODataSource(
            source_id=SOURCE_MIAMOR,
            base_url=settings.odata_miamor_url,
            username=settings.odata_miamor_user,
            password=settings.odata_miamor_password,
            verify_ssl=settings.odata_miamor_verify_ssl,
        ),
    ]
    return [s for s in sources if s.base_url]


def encode_entity_path(entity_set: str) -> str:
    """Percent-encode Cyrillic entity set names for HTTP path."""
    return quote(entity_set, safe="/$()'=,")


class ODataClient:
    """HTTP client for 1C standard OData interface."""

    def __init__(self, source: ODataSource, timeout: float = 120.0) -> None:
        self.source = source
        self._client = httpx.Client(
            base_url=source.base_url if source.base_url.endswith("/") else source.base_url + "/",
            auth=(source.username, source.password) if source.username else None,
            timeout=timeout,
            verify=source.verify_ssl,
            headers={"Accept": "application/json"},
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> ODataClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def health(self) -> str:
        if not self.source.username:
            return "unconfigured"
        try:
            resp = self._client.get("", params={"$format": "json"})
            if resp.status_code == 200:
                return "ok"
            return f"http_{resp.status_code}"
        except Exception as exc:  # noqa: BLE001
            logger.warning("OData health failed for %s: %s", self.source.source_id, exc)
            return "error"

    def get_metadata(self) -> bytes:
        resp = self._client.get("$metadata")
        resp.raise_for_status()
        return resp.content

    def iter_entity(
        self,
        entity_set: str,
        *,
        select: Optional[str] = None,
        filter_expr: Optional[str] = None,
        expand: Optional[str] = None,
        order_by: Optional[str] = None,
        top: int = 500,
        max_pages: int = 10_000,
        start_skip: int = 0,
    ) -> Iterator[dict[str, Any]]:
        """
        Iterate entity set pages.

        This 1C publication typically omits odata.nextLink; pagination uses $skip.
        Always pass order_by for stable paging.
        """
        params: dict[str, str | int] = {"$format": "json", "$top": top}
        if select:
            params["$select"] = select
        if filter_expr:
            params["$filter"] = filter_expr
        if expand:
            params["$expand"] = expand
        if order_by:
            params["$orderby"] = order_by

        path = encode_entity_path(entity_set)
        skip = max(0, start_skip)
        for _page in range(max_pages):
            page_params = dict(params)
            if skip:
                page_params["$skip"] = skip
            resp = self._client.get(path, params=page_params)
            if resp.status_code >= 400:
                logger.error("OData %s failed: %s %s", entity_set, resp.status_code, resp.text[:300])
            resp.raise_for_status()
            value = resp.json().get("value", [])
            if not value:
                break
            for row in value:
                yield row
            if len(value) < top:
                break
            skip += len(value)

    def fetch_all(self, entity_set: str, **kwargs: Any) -> list[dict[str, Any]]:
        return list(self.iter_entity(entity_set, **kwargs))

    def iter_nav_collection(
        self,
        entity_set: str,
        ref_key: str,
        nav_name: str = "Товары",
        *,
        top: int = 500,
        max_pages: int = 100,
    ) -> Iterator[dict[str, Any]]:
        """
        Iterate tabular section via nested path Document_...(guid'{ref}')/Товары.

        $expand on tabular parts is rejected by this 1C publication; nested path works.
        """
        path = encode_entity_path(f"{entity_set}(guid'{ref_key}')/{nav_name}")
        skip = 0
        for _page in range(max_pages):
            params: dict[str, str | int] = {"$format": "json", "$top": top}
            if skip:
                params["$skip"] = skip
            resp = self._client.get(path, params=params)
            if resp.status_code >= 400:
                logger.error(
                    "OData nav %s/%s failed: %s %s",
                    entity_set,
                    nav_name,
                    resp.status_code,
                    resp.text[:300],
                )
            resp.raise_for_status()
            value = resp.json().get("value", [])
            if not value:
                break
            for row in value:
                yield row
            if len(value) < top:
                break
            skip += len(value)

    def catalog_name_map(
        self,
        entity_set: str,
        *,
        select: str = "Ref_Key,Description",
        top: int = 500,
    ) -> dict[str, str]:
        """Ref_Key -> Description for lookup catalogs (e.g. warehouses)."""
        result: dict[str, str] = {}
        for row in self.iter_entity(entity_set, select=select, order_by="Ref_Key", top=top):
            ref = str(row.get("Ref_Key") or "")
            name = row.get("Description")
            if ref and name:
                result[ref] = str(name)
        return result
