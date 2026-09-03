# Вторая база 1С

1. Опубликовать базу аналогично `test3_asil`.
2. Тем же EPF включить тот же состав OData.
3. В `.env`:

```
ODATA_MIAMOR_URL=https://.../odata/standard.odata/
ODATA_MIAMOR_USER=...
ODATA_MIAMOR_PASSWORD=...
ODATA_MIAMOR_VERIFY_SSL=false
```

4. `POST /api/v1/sync/run?full=true&source_id=miamor`
5. В UI контрагенты фильтруются по `source_id` (API `/api/v1/counterparties?source_id=miamor`).
