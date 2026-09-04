# Security & NFR checklist (этап 4)

## Аутентификация
- JWT access 1ч / refresh 7д
- bcrypt cost via passlib
- lockout после 5 неудачных попыток на 15 минут
- роли: admin, regional_director, manager, analytic

## Данные
- HTTPS на reverse proxy (prod)
- OData credentials и ключ LLM только в `.env` / админке (не в git)
- `1c.txt` в `.gitignore`
- security headers middleware в FastAPI

## OData
- IP whitelist на стороне IIS/1С
- минимальные права сервисного пользователя (чтение)
- ротация пароля каждые 90 дней (операционный процесс)
- health: `GET /api/v1/health` → `odata`

## Производительность
- Redis для брокера Celery
- пагинация OData `$top`
- индексы PostgreSQL по ТЗ §4.2

## Резервное копирование (prod)
- hourly incremental / daily full PostgreSQL
- проверка restore ежемесячно

## Мониторинг
- `/api/v1/health`
- Celery task errors в логах worker
- алерты: OData down, sync failed (подключить Slack/Email при деплое)
