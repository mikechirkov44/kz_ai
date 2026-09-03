"""Sample realization dates across $skip pages to estimate walk cost."""
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
        for skip in (0, 100, 500, 1000, 2000, 5000, 10000, 20000, 50000):
            resp = client.get(
                path,
                params={
                    "$format": "json",
                    "$top": 3,
                    "$skip": skip,
                    "$orderby": "Ref_Key",
                    "$filter": "Posted eq true",
                    "$select": "Ref_Key,Number,Date,Posted",
                },
            )
            print(f"skip={skip} status={resp.status_code}")
            if resp.status_code != 200:
                print(" ", resp.text[:200].replace("\n", " "))
                continue
            rows = resp.json().get("value", [])
            if not rows:
                print("  empty")
                break
            for row in rows:
                print(" ", row.get("Number"), row.get("Date"), row.get("Ref_Key")[:8])

        # Expand warehouse?
        resp = client.get(
            path,
            params={
                "$format": "json",
                "$top": 1,
                "$expand": "Склад",
                "$select": "Ref_Key,Number,Date,Склад_Key",
            },
        )
        print("expand Склад", resp.status_code)
        if resp.status_code == 200:
            print(resp.json().get("value", [])[:1])
        else:
            print(resp.text[:300])


if __name__ == "__main__":
    main()
