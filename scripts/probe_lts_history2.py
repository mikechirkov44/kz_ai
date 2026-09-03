"""Probe LTS history: expand Значение, paging, filters."""
from __future__ import annotations

import json
from urllib.parse import quote

import httpx
from _creds import load_1c_creds

USER, PASSWORD = load_1c_creds()
BASE = "https://miamor.keenetic.pro:777/test3_asil/odata/standard.odata/"
ENTITY = "InformationRegister_ИсторияИзмененияЖЦТ"


def main() -> None:
    with httpx.Client(base_url=BASE, auth=(USER, PASSWORD), verify=False, timeout=120.0) as client:
        path = quote(ENTITY, safe="/$()'=,")
        resp = client.get(
            path,
            params={
                "$format": "json",
                "$top": 3,
                "$expand": "Значение",
                "$select": "Period,Номенклатура_Key,Значение_Key",
            },
        )
        print("expand Значение", resp.status_code)
        if resp.status_code == 200:
            for row in resp.json().get("value", []):
                print(json.dumps(row, ensure_ascii=False, default=str)[:500])
        else:
            print(resp.text[:400])

        # Catalog_ЮС_ЖЦТ sample for one key
        sample = client.get(
            path,
            params={"$format": "json", "$top": 1},
        ).json()["value"][0]
        val_key = sample["Значение_Key"]
        lts_path = quote("Catalog_ЮС_ЖЦТ", safe="/$()'=,")
        lts = client.get(
            lts_path,
            params={
                "$format": "json",
                "$filter": f"Ref_Key eq guid'{val_key}'",
                "$select": "Ref_Key,Description",
            },
        )
        print("lts lookup", lts.status_code, lts.text[:300])

        # Count-ish via large skip
        for skip in (0, 5000, 20000, 50000, 100000):
            r = client.get(
                path,
                params={"$format": "json", "$top": 1, "$skip": skip, "$orderby": "Period"},
            )
            if r.status_code != 200:
                print("skip", skip, r.status_code, r.text[:200].replace("\n", " "))
                break
            rows = r.json().get("value", [])
            if not rows:
                print("skip", skip, "empty")
                break
            print("skip", skip, rows[0].get("Period"), rows[0].get("Номенклатура_Key")[:8])


if __name__ == "__main__":
    main()
