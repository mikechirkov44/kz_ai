# OData mapping — актуализация по live $metadata (test3_asil)

**Проверено:** 2026-09-03  
**Auth:** Basic (учётка в `.env` / `1c.txt`, не в репозитории)
**Metadata:** [`docs/odata-metadata.xml`](odata-metadata.xml)

## Рабочие entity sets

| Entity set | Статус |
|---|---|
| `Catalog_Номенклатура` | OK |
| `Catalog_Контрагенты` | OK |
| `Catalog_МагазиныКонтрагентов` | OK (магазины, Owner_Key → контрагент) |
| `Catalog_ЮС_ЖЦТ` | OK |
| `InformationRegister_ИсторияИзмененияЖЦТ` | OK (Period = дата смены ЖЦТ) |
| `Document_РеализацияТоваровУслуг` (+ `_Товары`) | OK |
| `Document_ВозвратТоваровОтПокупателя` (+ `_Товары`) | OK |
| `Document_ЗаказКлиента` (+ `_Товары`) | OK |
| `Document_ПоступлениеТоваровУслуг` (+ `_Товары`) | OK |
| `Document_ПоступлениеПродукцииИзПроизводства` (+ `_Товары`) | OK — **не** `ПоступлениеИзПроизводства` |

## Catalog_Номенклатура → nomenclature

| OData | БД | Примечание |
|---|---|---|
| `Ref_Key` | `onec_ref` | |
| `Артикул` | `article` | |
| `Description` | `name` | |
| `Акция` | `is_promo` | bool/null |
| `Весовой` | `is_weighted` | |
| `ЮС_ЖЦТ` / Description | `lts` | `$expand=ЮС_ЖЦТ` |
| `КС_Направление` / Description | `direction` | фильтр ИМПЕРИАЛ… |
| `ЮС_ЦветМеталла` / Description | `metal_color` | |
| `ТипИзделия` / Description | `wear_type` | = тип ношения |
| `Проба` / Description | `assay` | |
| `InformationRegister_ИсторияИзмененияЖЦТ.Period` | `lts_date` | отдельный sync (позже) |

Поля `Modified` **нет** — инкремент по дате недоступен, каталоги синхронизируем полным обходом.

`$select` / `$expand`: см. `NOM_SELECT` / `NOM_EXPAND` в `backend/app/odata/mapping.py`.

## Catalog_Контрагенты → counterparty

| OData | БД |
|---|---|
| `Ref_Key` | `onec_ref` |
| `Description` | `name` |
| `ГоловнойКонтрагент_Key` | `head_counterparty_onec_ref` |
| `Parent_Key` | `parent_onec_ref` |
| `IsFolder` | `is_folder` |
| `ТипРаботыКонтрагента` | `work_type` (Прирост=Рост) |
| `ПроцентТипаРаботы` | `work_type_percent` |
| `Catalog_МагазиныКонтрагентов` | `shops` JSON |

Признака «Участвует в акции» на справочнике контрагентов в metadata **не найдено** — нужна отдельная логика (документ/регистр акций) или ручная пометка.

## Документы движения (кратко)

- Реализация/возврат: `Контрагент_Key`, `Склад`/`Склад_Key`, ТЧ `Товары`: `Номенклатура_Key`, `Количество`, `Цена`, `Сумма`, `СерияНоменклатуры`, `ЗаказКлиента_Key` (в реализации).
- Признак «Не учитывать при оборачиваемости» в шапке **не найден** под ожидаемым именем — уточнить у аналитика 1С / доп. реквизит.
- Поступление из производства: `Document_ПоступлениеПродукцииИзПроизводства_Товары.ЗаказКлиента_Key` + `СерияНоменклатуры`.

## source_id

- `asil` → test3_asil  
- `miamor` → вторая база (TBD)

## Пагинация

Публикация **не отдаёт** `odata.nextLink`. Клиент листает через `$skip` + `$orderby=Ref_Key`.
