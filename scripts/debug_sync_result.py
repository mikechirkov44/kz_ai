import json
import sqlite3

import httpx
from _creds import load_1c_creds

user, password = load_1c_creds()

with httpx.Client(
    base_url="https://miamor.keenetic.pro:777/test3_asil/odata/standard.odata/",
    auth=(user, password),
    verify=False,
    timeout=60,
) as client:
    resp = client.get(
        "Catalog_Номенклатура",
        params={
            "$top": 200,
            "$format": "json",
            "$select": "Ref_Key,Description,Артикул,IsFolder,DeletionMark",
        },
    )
    print("status", resp.status_code)
    data = resp.json()
    print("next", data.get("odata.nextLink") or data.get("@odata.nextLink"))
    print("len", len(data.get("value", [])))

con = sqlite3.connect("data/trial_sync.db")
cur = con.cursor()
print("total", cur.execute("select count(*) from nomenclature").fetchone())
