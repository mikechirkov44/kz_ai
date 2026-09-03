"""Sample LTS history date range and Catalog_ЮС_ЖЦТ map."""
from __future__ import annotations

from urllib.parse import quote

import httpx
from _creds import load_1c_creds

USER, PASSWORD = load_1c_creds()
BASE = "https://miamor.keenetic.pro:777/test3_asil/odata/standard.odata/"


def main() -> None:
    with httpx.Client(base_url=BASE, auth=(USER, PASSWORD), verify=False, timeout=120.0) as client:
        hist = quote("InformationRegister_ИсторияИзмененияЖЦТ", safe="/$()'=,")
        # collect unique periods from a few pages
        periods = set()
        skip = 0
        total = 0
        while skip < 30000:
            r = client.get(
                hist,
                params={"$format": "json", "$top": 500, "$skip": skip, "$orderby": "Period"},
            )
            if r.status_code != 200:
                print("page fail", skip, r.status_code)
                break
            rows = r.json().get("value", [])
            if not rows:
                break
            total += len(rows)
            for row in rows:
                periods.add(row.get("Period", "")[:10])
            skip += len(rows)
            if len(rows) < 500:
                break
        print("history rows sampled", total, "unique dates", sorted(periods)[:20], "...", sorted(periods)[-5:])

        lts = quote("Catalog_ЮС_ЖЦТ", safe="/$()'=,")
        r = client.get(lts, params={"$format": "json", "$top": 50, "$select": "Ref_Key,Description,Code"})
        print("ЮС_ЖЦТ status", r.status_code)
        for row in r.json().get("value", [])[:15]:
            print(" ", row.get("Description"), row.get("Ref_Key")[:8])


if __name__ == "__main__":
    main()
