"""Sample OData entities via httpx (handles encoding)."""
from __future__ import annotations

import json

import httpx
from _creds import load_1c_creds

USER, PASSWORD = load_1c_creds()
BASE = "https://miamor.keenetic.pro:777/test3_asil/odata/standard.odata/"


def main() -> None:
    with httpx.Client(base_url=BASE, auth=(USER, PASSWORD), verify=False, timeout=90.0) as client:
        r = client.get(
            "Catalog_Номенклатура",
            params={
                "$top": 2,
                "$format": "json",
                "$select": "Ref_Key,Description,Артикул,Акция,Весовой,КС_Направление_Key,ЮС_ЖЦТ_Key,ЮС_ЦветМеталла_Key,ТипИзделия_Key,Проба_Key,DataVersion",
                "$expand": "ЮС_ЖЦТ,КС_Направление,ЮС_ЦветМеталла,ТипИзделия,Проба",
            },
        )
        print("NOM status", r.status_code)
        if r.status_code != 200:
            print(r.text[:500])
        else:
            for row in r.json().get("value", []):
                clean = {k: v for k, v in row.items() if "navigationLinkUrl" not in k}
                print(json.dumps(clean, ensure_ascii=False, default=str)[:1500])
                print("---")

        r2 = client.get(
            "Catalog_Контрагенты",
            params={
                "$top": 3,
                "$filter": "IsFolder eq false",
                "$format": "json",
                "$select": "Ref_Key,Description,IsFolder,ГоловнойКонтрагент_Key,Parent_Key,ТипРаботыКонтрагента,ПроцентТипаРаботы,КоличествоТТ",
            },
        )
        print("CP status", r2.status_code)
        for row in r2.json().get("value", [])[:3]:
            print(json.dumps(row, ensure_ascii=False, default=str)[:600])


if __name__ == "__main__":
    main()
