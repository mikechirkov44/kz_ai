"""Probe InformationRegister_ИсторияИзмененияЖЦТ shape."""
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
        attempts = [
            {"$top": 3},
            {"$top": 3, "$orderby": "Period desc"},
            {"$top": 3, "$orderby": "Period"},
            {"$top": 5, "$expand": "Номенклатура,ЮС_ЖЦТ"},
        ]
        for params in attempts:
            resp = client.get(path, params={"$format": "json", **params})
            print("try", params, "->", resp.status_code)
            if resp.status_code != 200:
                print(resp.text[:400].replace("\n", " "))
                continue
            rows = resp.json().get("value", [])
            print("rows", len(rows))
            if not rows:
                continue
            row = rows[0]
            keys = sorted(k for k in row if "navigationLinkUrl" not in k)
            print("keys:", keys)
            print(json.dumps(row, ensure_ascii=False, default=str)[:1200])
            break

        # paging sample
        resp = client.get(
            path,
            params={"$format": "json", "$top": 2, "$skip": 1000, "$orderby": "Period"},
        )
        print("skip=1000", resp.status_code)
        if resp.status_code == 200:
            for row in resp.json().get("value", []):
                print(
                    " ",
                    row.get("Period"),
                    row.get("Номенклатура_Key") or row.get("Номенклатура"),
                    {k: row[k] for k in row if "ЖЦТ" in k or "LTS" in k.upper()},
                )


if __name__ == "__main__":
    main()
