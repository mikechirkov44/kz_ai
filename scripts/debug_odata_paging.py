import json

import httpx
from _creds import load_1c_creds

user, password = load_1c_creds()
client = httpx.Client(
    base_url="https://miamor.keenetic.pro:777/test3_asil/odata/standard.odata/",
    auth=(user, password),
    verify=False,
    timeout=60,
)

r = client.get(
    "Catalog_Номенклатура",
    params={"$top": 50, "$skip": 200, "$format": "json", "$select": "Ref_Key,Description,Артикул,IsFolder"},
)
print("skip200 status", r.status_code, "len", len(r.json().get("value", [])))
print("sample", json.dumps(r.json().get("value", [])[:2], ensure_ascii=False))
client.close()
