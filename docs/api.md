# OpenAPI

При запущенном API: http://localhost:8000/docs (Swagger) и `/openapi.json`.

## Группы

| Prefix | Назначение |
|---|---|
| `/api/v1/auth/*` | login / refresh / users |
| `/api/v1/uploads/*` | Excel |
| `/api/v1/reports/*` | мотивация, оборачиваемость, кварталы, факт, рекомендации |
| `/api/v1/sync/*` | статус и ручной запуск |
| `/api/v1/counterparties*` | список + promo flag |
| `/api/v1/digest/run` | превью / отправка weekly digest |
| `/api/v1/health` | healthcheck |

## Квартальные планы

- `GET /api/v1/reports/quarterly-plans?year=&quarter=`
- `POST /api/v1/reports/quarterly-plans` — upsert
- `POST /api/v1/reports/quarterly-plans/bulk` — массовый upsert
- `DELETE /api/v1/reports/quarterly-plans?year=&quarter=&counterparty_id=`
- `DELETE /api/v1/reports/quarterly-plans/{plan_id}`

## Sync / OData settings

- `GET /api/v1/odata/connections` — список подключений (пароль не отдаётся, только `password_set`)
- `PUT /api/v1/odata/connections/{source_id}` — сохранить URL / логин / пароль / enabled
- `POST /api/v1/odata/connections/{source_id}/test` — проверка связи
- `POST /api/v1/sync/run?full=&source_id=&background=&catalogs_only=`
- `background=true` ставит задачу в Celery (`SYNC_ENABLED=true` + worker)

Рабочая база сейчас — `asil`. `miamor` в форме есть, по умолчанию `enabled=false` (подключаем в конце).

## Promo

- `PATCH /api/v1/counterparties/{id}/promo`
- `POST /api/v1/counterparties/promo/bulk`
- `GET /api/v1/counterparties?promo_only=&source_id=&q=`

## Catalogs / documents

- `GET /api/v1/catalogs/nomenclature`
- `GET /api/v1/catalogs/counterparties`
- `GET /api/v1/documents/realizations|returns|orders|production` (+ detail by source_id/onec_ref)

## Reports extras

- `GET /api/v1/reports/turnover-matrix` — мультимесячная матрица
- `GET /api/v1/reports/quarterly-summary` — §5.4 блоки цвет/ЖЦТ/тип

## Excel export

- `GET /api/v1/reports/motivation.xlsx?...`
- `GET /api/v1/reports/turnover-matrix.xlsx?...`
- `GET /api/v1/reports/quarterly-plans.xlsx?...`
- `GET /api/v1/catalogs/nomenclature.xlsx?...`
- `GET /api/v1/catalogs/counterparties.xlsx?...`

## Rate limit

- Login: 10 req/min/IP (`RATE_LIMIT_LOGIN_PER_MINUTE`)
- API `/api/v1/*`: 180 req/min/IP (`RATE_LIMIT_API_PER_MINUTE`)
- 429 Too Many Requests
- `GET /api/v1/uploads/templates/{sales|stocks|both|promo_motivation}`
