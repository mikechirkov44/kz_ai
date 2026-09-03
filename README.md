# Веб-сервис аналитики «Акции по клиентам»

Стек: FastAPI + React + PostgreSQL + Redis + Celery. Интеграция с двумя базами 1С через OData (`source_id`).

## Быстрый старт

1. Скопировать `.env.example` → `.env`, заполнить OData (см. `1c.txt`, не коммитить).
2. `docker compose up --build`
3. API: http://localhost:8000/docs  
   UI: http://localhost:5173  
   Логин по умолчанию: `admin@example.com` / `admin12345`

## Этап 0 — OData

См. [docs/odata-setup.md](docs/odata-setup.md) и [docs/odata-mapping.md](docs/odata-mapping.md).

```bash
python scripts/fetch_odata_metadata.py
```

`SYNC_ENABLED=false` по умолчанию — сначала маппинг, затем ручной sync из Админки / `POST /api/v1/sync/run`.

## Локальные тесты backend

```bash
cd backend
pip install -r requirements.txt
pytest -q --cov=app/domain --cov-fail-under=90
```

## Структура

- `backend/app` — API, domain, OData, sync, reports, AI rules, workers
- `frontend/src` — SPA (дашборд, загрузки, мотивация, оборачиваемость, кварталы, рекомендации, админ)
- `docs/` — маппинг, безопасность, runbooks

## Вторая база 1С

Заполнить `ODATA_MIAMOR_*` в `.env`. Метаданные те же; данные пишутся с `source_id=miamor`.
