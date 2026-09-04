# OpenAPI

При запущенном API: http://localhost:8000/docs (Swagger) и `/openapi.json`.

## Группы

| Prefix | Назначение |
|---|---|
| `/api/v1/auth/*` | login / refresh / me / users / managers |
| `/api/v1/uploads/*` | Excel |
| `/api/v1/reports/*` | мотивация, оборачиваемость, кварталы, факт, рекомендации, теплокарта |
| `/api/v1/sync/*` | статус и ручной запуск |
| `/api/v1/counterparties*` | список + promo + менеджер |
| `/api/v1/audit` | журнал аудита (admin) |
| `/api/v1/digest/run` | превью / отправка weekly digest |
| `/api/v1/health` | healthcheck |
| `/api/v1/llm/settings` | подключение LLM (admin) |
| `/api/v1/mail/settings` | рассылка SMTP (admin) |

## Квартальные планы

- `GET /api/v1/reports/quarterly-plans?year=&quarter=`
- `POST /api/v1/reports/quarterly-plans` — upsert
- `POST /api/v1/reports/quarterly-plans/bulk` — массовый upsert
- `DELETE /api/v1/reports/quarterly-plans?year=&quarter=&counterparty_id=`
- `DELETE /api/v1/reports/quarterly-plans/{plan_id}`

## Sync / OData settings

- `GET /api/v1/odata/sources` — список баз для фильтров (имя, `enabled`, без секретов; все роли)
- `GET /api/v1/odata/connections` — список подключений (пароль не отдаётся, только `password_set`)
- `POST /api/v1/odata/connections` — добавить подключение (имя; технический `source_id` выдаётся сам)
- `PUT /api/v1/odata/connections/{source_id}` — сохранить имя / URL / логин / пароль / enabled
- `POST /api/v1/odata/connections/{source_id}/test` — проверка связи
- `GET /api/v1/llm/settings` — настройки LLM (ключ не отдаётся, только `api_key_set`)
- `PUT /api/v1/llm/settings` — сохранить URL / модель / ключ / enabled
- `POST /api/v1/llm/settings/test` — проверка связи (можно передать черновик формы)
- `GET /api/v1/mail/settings` — настройки рассылки (пароль SMTP не отдаётся)
- `PUT /api/v1/mail/settings` — состав письма, SMTP, получатели, авторассылка
- `POST /api/v1/mail/settings/test` — проверка SMTP
- `GET /api/v1/sync/status` — строки по базе × объекту, включая `since_date` и `date_filter`
- `PATCH /api/v1/sync/since` — `{ source_id, entity, since_date }` (пустая дата = без ограничения; не удаляет уже загруженные строки)
- `POST /api/v1/sync/run?full=&source_id=&background=&catalogs_only=`
- `background=true` ставит задачу в Celery (`SYNC_ENABLED=true` + worker)

Имя базы задаётся в админке и показывается в фильтрах. Технический `source_id` в API остаётся для синхронизированных строк.

## Promo

- `PATCH /api/v1/counterparties/{id}/promo`
- `POST /api/v1/counterparties/promo/bulk`
- `PATCH /api/v1/counterparties/{id}/manager`
- `POST /api/v1/counterparties/manager/bulk`
- `GET /api/v1/counterparties?promo_only=&source_id=&q=`
- `GET /api/v1/auth/users` / `POST` / `PATCH /api/v1/auth/users/{id}` (admin)
- `GET /api/v1/auth/managers`
- `GET /api/v1/audit`

## Catalogs / documents

- `GET /api/v1/catalogs/nomenclature`
- `GET /api/v1/catalogs/counterparties`
- `GET /api/v1/documents/realizations|returns|orders|production` — `q=` поиск (номер, контрагент, склад)

## Reports extras

- `GET /api/v1/reports/motivation?year=&month=&counterparty_id=&source_id=` — без `counterparty_id` свод по участникам акции
- `GET /api/v1/reports/fact-shipments?year=&quarter=&counterparty_id=` — только участники акции; без `counterparty_id` все promo-клиенты за квартал (менеджер — только свои)
- `GET /api/v1/reports/turnover-matrix` — мультимесячная матрица
- `GET /api/v1/reports/quarterly-summary` — итоговый отчёт: матрица цвет/ЖЦТ/тип, прошлые кварталы, комментарий, план след. Q, рекомендации
- `GET /api/v1/reports/quarterly-summary.xlsx`
- `GET /api/v1/reports/quarterly-comments?year=&quarter=&counterparty_id=` — история комментариев
- `POST /api/v1/reports/quarterly-comments` — добавить комментарий (на экране показывается последний)
- `GET /api/v1/reports/dwell-heatmap` — теплокарта пролежки
- `GET /api/v1/reports/cbr-rates` — курсы ЦБ РФ (USD, EUR, KZT за 1 единицу)
- `GET /api/v1/reports/recommendations` — rule-based рекомендации; если LLM включён в админке, у пунктов появляется `llm_comment`, в ответе `llm_status`: `off` / `ok` / `error`

## Excel export

- `GET /api/v1/reports/motivation.xlsx?...`
- `GET /api/v1/reports/turnover-matrix.xlsx?...`
- `GET /api/v1/reports/quarterly-plans.xlsx?...`
- `GET /api/v1/reports/quarterly-summary.xlsx?...`
- `GET /api/v1/catalogs/nomenclature.xlsx?...`
- `GET /api/v1/catalogs/counterparties.xlsx?...`

## Rate limit

- Login: 10 req/min/IP (`RATE_LIMIT_LOGIN_PER_MINUTE`)
- API `/api/v1/*`: 180 req/min/IP (`RATE_LIMIT_API_PER_MINUTE`)
- 429 Too Many Requests

## Uploads

- `GET /api/v1/uploads` — история загрузок (менеджер — свои)
- `GET /api/v1/uploads/{id}/file` — исходный Excel, если ещё на диске
- `GET /api/v1/uploads/{id}/errors.xlsx`
- `GET /api/v1/uploads/templates/{sales|stocks|both|promo_motivation}`
