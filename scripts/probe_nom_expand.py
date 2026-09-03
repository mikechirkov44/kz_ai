"""Diagnose why nomenclature expand fields are often null."""
from __future__ import annotations

import json
from collections import Counter
from urllib.parse import quote

import httpx
from _creds import load_1c_creds

USER, PASSWORD = load_1c_creds()
BASE = "https://miamor.keenetic.pro:777/test3_asil/odata/standard.odata/"
ENTITY = "Catalog_Номенклатура"
SELECT = (
    "Ref_Key,Description,Артикул,IsFolder,DeletionMark,"
    "КС_Направление_Key,ЮС_ЖЦТ_Key,ЮС_ЦветМеталла_Key,ТипИзделия_Key,Проба_Key"
)
EXPAND = "ЮС_ЖЦТ,КС_Направление,ЮС_ЦветМеталла,ТипИзделия,Проба"


def main() -> None:
    with httpx.Client(base_url=BASE, auth=(USER, PASSWORD), verify=False, timeout=120.0) as client:
        path = quote(ENTITY, safe="/$()'=,")
        resp = client.get(
            path,
            params={
                "$format": "json",
                "$top": 30,
                "$select": SELECT,
                "$expand": EXPAND,
                "$filter": "IsFolder eq false",
                "$orderby": "Ref_Key",
            },
        )
        print("status", resp.status_code)
        if resp.status_code != 200:
            print(resp.text[:500])
            return
        rows = resp.json().get("value", [])
        print("rows", len(rows))
        filled = Counter()
        for i, row in enumerate(rows[:5]):
            print("--- sample", i, row.get("Артикул") or row.get("Description"))
            for nav in ("ЮС_ЖЦТ", "КС_Направление", "ЮС_ЦветМеталла", "ТипИзделия", "Проба"):
                key = f"{nav}_Key"
                val = row.get(nav)
                print(f"  {key}={row.get(key)}")
                print(f"  {nav} type={type(val).__name__} val={json.dumps(val, ensure_ascii=False, default=str)[:200] if val is not None else None}")
                if isinstance(val, dict) and val.get("Description"):
                    filled[nav] += 1
                elif row.get(key) and str(row.get(key)) != "00000000-0000-0000-0000-000000000000":
                    filled[f"{nav}_key_only"] += 1

        # larger sample stats without printing
        resp2 = client.get(
            path,
            params={
                "$format": "json",
                "$top": 200,
                "$select": SELECT,
                "$expand": EXPAND,
                "$filter": "IsFolder eq false",
                "$orderby": "Ref_Key",
            },
        )
        rows2 = resp2.json().get("value", [])
        stats = Counter()
        for row in rows2:
            for nav in ("ЮС_ЖЦТ", "КС_Направление", "ЮС_ЦветМеталла", "ТипИзделия", "Проба"):
                key = f"{nav}_Key"
                guid = str(row.get(key) or "")
                empty = not guid or guid == "00000000-0000-0000-0000-000000000000"
                nav_obj = row.get(nav)
                has_desc = isinstance(nav_obj, dict) and bool(nav_obj.get("Description"))
                if empty:
                    stats[f"{nav}:empty_key"] += 1
                elif has_desc:
                    stats[f"{nav}:expanded"] += 1
                else:
                    stats[f"{nav}:key_no_expand"] += 1
        print("stats n=", len(rows2))
        for k, v in sorted(stats.items()):
            print(f"  {k}={v}")

        # catalog lookups
        for catalog in (
            "Catalog_ЮС_ЖЦТ",
            "Catalog_КС_Направление",
            "Catalog_ЮС_ЦветМеталла",
            "Catalog_ТипИзделия",
            "Catalog_Пробы",
            "Catalog_Проба",
        ):
            cpath = quote(catalog, safe="/$()'=,")
            cr = client.get(cpath, params={"$format": "json", "$top": 2, "$select": "Ref_Key,Description"})
            print(catalog, cr.status_code, end=" ")
            if cr.status_code == 200:
                vals = cr.json().get("value", [])
                print("sample", [v.get("Description") for v in vals])
            else:
                print(cr.text[:120].replace("\n", " "))


if __name__ == "__main__":
    main()
