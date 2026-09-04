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
| `ЮС_ЖЦТ_Key` → `Catalog_ЮС_ЖЦТ` | `lts` | `$expand` пустой → lookup |
| `КС_Направление_Key` → `Catalog_КС_Направления` | `direction` | не `Catalog_КС_Направление` |
| `ЮС_ЦветМеталла_Key` → `Catalog_ЮС_ЦветМеталла` | `metal_color` | |
| `ТипИзделия_Key` → `Catalog_ТипыИзделий` | `wear_type` | не `Catalog_ТипИзделия` |
| `Проба_Key` → `Catalog_Пробы` | `assay` | не `Catalog_Проба` |
| `InformationRegister_ИсторияИзмененияЖЦТ.Period` | `lts_date` | последняя Period на номенклатуру |
| `Значение_Key` → `Catalog_ЮС_ЖЦТ.Description` | `lts` | дополняет/обновляет текущий ЖЦТ |

Поля `Modified` **нет** — инкремент по дате недоступен, каталоги синхронизируем полным обходом.

`$select`: см. `NOM_SELECT` в `backend/app/odata/mapping.py`. `$expand` навигации на live **не возвращает Description** — имена резолвятся через справочники выше.

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

Признака «Участвует в акции» на справочнике контрагентов в metadata **не найдено** — `counterparty.is_promo` выставляется при загрузке Excel (`uploads.py`) или через admin API `PATCH /api/v1/counterparties/{id}/promo` / `POST /api/v1/counterparties/promo/bulk`. Для trial/UAT — скрипт `scripts/seed_reports_from_realizations.py`.

## Документы движения (кратко)

- **Шапка:** `Document_РеализацияТоваровУслуг` / `Document_ВозвратТоваровОтПокупателя` (`Posted eq true`).
- **Строки:** nested path `Document_...(guid'{Ref_Key}')/Товары` — `$expand=Товары` на этой публикации **отклоняется**.
- **Дата:** `$filter` по `Date` **запрещён** → фильтр `>= 2023-01-01` на стороне клиента; для пробного sync можно `start_skip≈4500`.
- Реализация: склад `Склад_Key` → имя через `Catalog_Склады`.
- Возврат: склад шапки `СкладОрдер_Key`, в строках — `Склад_Key`.
- ТЧ: `Номенклатура_Key`, `Количество`, `Цена`, `Сумма`, `СерияНоменклатуры_Key`, `ЗаказКлиента_Key` (в реализации).
- Признак «Не учитывать при оборачиваемости» в шапке **не найден**.
- Поступление из производства: `Document_ПоступлениеПродукцииИзПроизводства` + nested `/Товары`.

## История ЖЦТ

- Entity: `InformationRegister_ИсторияИзмененияЖЦТ` (`Period`, `Номенклатура_Key`, `Значение_Key`).
- На live-базе ~18k записей с ~2025-03 (более ранней истории в публикации нет).
- Sync: `sync_lts_history` — для каждой номенклатуры берётся **последняя** `Period` → `lts_date`, имя ЖЦТ из `Catalog_ЮС_ЖЦТ`.
- `$expand=Значение` отвечает 200, но объект не вкладывает → резолв через каталог.

- `asil` → test3_asil  
- `miamor` → вторая база (TBD)

## Пагинация

Публикация **не отдаёт** `odata.nextLink`. Клиент листает через `$skip` + `$orderby=Ref_Key`.
