"""Probe date filters and warehouse lookup for documents."""
from __future__ import annotations

from urllib.parse import quote

import httpx
from _creds import load_1c_creds

USER, PASSWORD = load_1c_creds()
BASE = "https://miamor.keenetic.pro:777/test3_asil/odata/standard.odata/"
ENTITY = "Document_РеализацияТоваровУслуг"


def main() -> None:
    with httpx.Client(base_url=BASE, auth=(USER, PASSWORD), verify=False, timeout=120.0) as client:
        path = quote(ENTITY, safe="/$()'=,")
        filters = [
            None,
            "Posted eq true",
            "DeletionMark eq false",
            "year(Date) ge 2023",
            "Date gt datetime'2023-01-01T00:00:00'",
            "Date ge datetime'2023-01-01'",
            "Number ne ''",
        ]
        for filt in filters:
            params: dict[str, str | int] = {"$format": "json", "$top": 3, "$orderby": "Date desc"}
            if filt:
                params["$filter"] = filt
            resp = client.get(path, params=params)
            print("filter=", filt, "status=", resp.status_code)
            if resp.status_code != 200:
                print(" ", resp.text[:250].replace("\n", " "))
                continue
            rows = resp.json().get("value", [])
            for row in rows:
                print(" ", row.get("Number"), row.get("Date"), "posted=", row.get("Posted"))

        wh = quote("Catalog_Склады", safe="/$()'=,")
        wh_resp = client.get(wh, params={"$format": "json", "$top": 2, "$select": "Ref_Key,Description"})
        print("warehouses", wh_resp.status_code)
        if wh_resp.status_code == 200:
            print(wh_resp.json().get("value", [])[:2])
        else:
            print(wh_resp.text[:300])

        resp = client.get(path, params={"$format": "json", "$top": 5, "$orderby": "Date desc"})
        print("newest realizations:")
        for row in resp.json().get("value", []):
            print(" ", row.get("Number"), row.get("Date"), row.get("Posted"))


if __name__ == "__main__":
    main()
