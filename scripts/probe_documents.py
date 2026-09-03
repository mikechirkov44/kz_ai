"""Probe realization/return OData shape (test3_asil)."""
from __future__ import annotations

import json
from urllib.parse import quote

import httpx
from _creds import load_1c_creds

USER, PASSWORD = load_1c_creds()
BASE = "https://miamor.keenetic.pro:777/test3_asil/odata/standard.odata/"

DOCS = (
    ("Document_РеализацияТоваровУслуг", "Document_РеализацияТоваровУслуг_Товары"),
    ("Document_ВозвратТоваровОтПокупателя", "Document_ВозвратТоваровОтПокупателя_Товары"),
)
HEADER_KEYS = (
    "Ref_Key",
    "Number",
    "Date",
    "Posted",
    "DeletionMark",
    "Контрагент_Key",
    "Склад",
    "Склад_Key",
    "НеУчитыватьПриОборачиваемости",
)
LINE_KEYS = (
    "Ref_Key",
    "LineNumber",
    "Номенклатура_Key",
    "Количество",
    "Цена",
    "Сумма",
    "СерияНоменклатуры",
    "СерияНоменклатуры_Key",
    "Серия",
    "ЗаказКлиента_Key",
)


def _get(client: httpx.Client, entity: str, **params: str | int) -> httpx.Response:
    path = quote(entity, safe="/$()'=,")
    return client.get(path, params={"$format": "json", **params})


def main() -> None:
    with httpx.Client(base_url=BASE, auth=(USER, PASSWORD), verify=False, timeout=120.0) as client:
        for header_entity, line_entity in DOCS:
            print("=== HEADER", header_entity, "===")
            attempts = [
                {"$top": 2, "$orderby": "Ref_Key"},
                {"$top": 2},
                {"$top": 2, "$filter": "Posted eq true"},
                {"$top": 2, "$filter": "Date ge datetime'2024-01-01T00:00:00'"},
                {"$top": 2, "$select": "Ref_Key,Number,Date,Posted,DeletionMark,Контрагент_Key,Склад_Key"},
            ]
            headers: list[dict] = []
            for params in attempts:
                resp = _get(client, header_entity, **params)
                print("try", params, "->", resp.status_code)
                if resp.status_code != 200:
                    print(resp.text[:350])
                    continue
                headers = resp.json().get("value", [])
                print("headers", len(headers))
                break
            if not headers:
                continue
            row = headers[0]
            print("header keys:", sorted(k for k in row if "navigationLinkUrl" not in k)[:60])
            for key in HEADER_KEYS:
                if key in row:
                    print(f"  {key}=", repr(row[key])[:140])

            ref = row["Ref_Key"]
            print("=== LINES", line_entity, "for", ref, "===")
            for filt in (f"Ref_Key eq guid'{ref}'", None):
                params: dict[str, str | int] = {"$top": 5}
                if filt:
                    params["$filter"] = filt
                line_resp = _get(client, line_entity, **params)
                print("lines status", line_resp.status_code, "filter", filt)
                if line_resp.status_code != 200:
                    print(line_resp.text[:500])
                    continue
                lines = line_resp.json().get("value", [])
                print("lines", len(lines))
                if not lines:
                    continue
                line = lines[0]
                print("line keys:", sorted(k for k in line if "navigation" not in k)[:50])
                print(json.dumps({k: line.get(k) for k in LINE_KEYS}, ensure_ascii=False, default=str))
                break

            # Also try Document(guid)/Товары nested path
            nested = quote(f"{header_entity}(guid'{ref}')/Товары", safe="/$()'=,")
            nested_resp = client.get(nested, params={"$format": "json", "$top": 5})
            print("nested path status", nested_resp.status_code)
            if nested_resp.status_code == 200:
                print("nested lines", len(nested_resp.json().get("value", [])))
            else:
                print(nested_resp.text[:300])


if __name__ == "__main__":
    main()
