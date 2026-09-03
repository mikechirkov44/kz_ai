"""Sample filled nomenclature keys + resolve via plural catalogs."""
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
EMPTY = "00000000-0000-0000-0000-000000000000"


def filled(key: object) -> bool:
    return bool(key) and str(key) != EMPTY


def main() -> None:
    with httpx.Client(base_url=BASE, auth=(USER, PASSWORD), verify=False, timeout=120.0) as client:
        path = quote(ENTITY, safe="/$()'=,")
        stats = Counter()
        samples = []
        skip = 0
        while skip < 5000 and len(samples) < 5:
            resp = client.get(
                path,
                params={
                    "$format": "json",
                    "$top": 200,
                    "$skip": skip,
                    "$select": SELECT,
                    "$expand": EXPAND,
                    "$orderby": "Ref_Key",
                },
            )
            rows = resp.json().get("value", [])
            if not rows:
                break
            for row in rows:
                if row.get("IsFolder") or row.get("DeletionMark"):
                    continue
                has_dir = filled(row.get("КС_Направление_Key"))
                has_lts = filled(row.get("ЮС_ЖЦТ_Key"))
                has_type = filled(row.get("ТипИзделия_Key"))
                has_color = filled(row.get("ЮС_ЦветМеталла_Key"))
                has_assay = filled(row.get("Проба_Key"))
                if has_dir:
                    stats["has_direction"] += 1
                if has_lts:
                    stats["has_lts"] += 1
                if has_type:
                    stats["has_wear"] += 1
                if has_color:
                    stats["has_color"] += 1
                if has_assay:
                    stats["has_assay"] += 1
                stats["items"] += 1
                if has_dir and has_type and len(samples) < 5:
                    samples.append(row)
                # expand quality when key present
                for nav, key_name in (
                    ("ЮС_ЖЦТ", "ЮС_ЖЦТ_Key"),
                    ("КС_Направление", "КС_Направление_Key"),
                    ("ЮС_ЦветМеталла", "ЮС_ЦветМеталла_Key"),
                    ("ТипИзделия", "ТипИзделия_Key"),
                    ("Проба", "Проба_Key"),
                ):
                    if not filled(row.get(key_name)):
                        continue
                    nav_obj = row.get(nav)
                    if isinstance(nav_obj, dict) and nav_obj.get("Description"):
                        stats[f"{nav}:expanded_ok"] += 1
                    else:
                        stats[f"{nav}:key_no_desc"] += 1
            skip += len(rows)

        print("stats", dict(stats))
        for row in samples:
            print("---", row.get("Артикул"), row.get("Description"))
            print(json.dumps({k: row.get(k) for k in SELECT.split(",") + EXPAND.split(",")}, ensure_ascii=False, default=str)[:900])

        for catalog in (
            "Catalog_КС_Направления",
            "Catalog_ТипыИзделий",
            "Catalog_Пробы",
            "Catalog_ЮС_ЦветМеталла",
            "Catalog_ЮС_ЖЦТ",
        ):
            cpath = quote(catalog, safe="/$()'=,")
            cr = client.get(cpath, params={"$format": "json", "$top": 8, "$select": "Ref_Key,Description"})
            print(catalog, cr.status_code, [x.get("Description") for x in cr.json().get("value", [])])


if __name__ == "__main__":
    main()
