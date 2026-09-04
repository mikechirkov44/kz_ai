# Runbook — Акции по клиентам

Операционные шаги для локального/staging окружения.

## Подъём

```bash
docker compose up -d --build
```

Сервисы: API `:8000`, frontend `:5173`, PostgreSQL, Redis, Celery worker/beat.

Health: `GET http://localhost:8000/api/v1/admin/health` (нужен JWT admin) или смотреть OpenAPI `/docs`.

Логин по умолчанию (dev): `admin@example.com` / из `.env` (`ADMIN_PASSWORD`).

## OData / sync

1. Админ → **Подключения 1С**: URL, логин, пароль, «Проверить связь».
2. **Инкремент** или **Полный sync** для `asil`.
3. Участников акции отметить `is_promo` (если не пришло из 1С).

Вторая база `miamor`: см. `docs/second-base.md` (в конце проекта).

Расписание Celery: инкремент каждые 15 мин, полный sync 02:00, digest пн 08:00 (Asia/Almaty).

## Excel-загрузки

1. Данные → Загрузка Excel.
2. Скачать шаблон нужного типа.
3. Загрузить файл; при ошибках — `errors.xlsx`.

Типы: продажи, остатки, both, доп. мотивация.

## Отчёты

| Отчёт | Экран | Экспорт |
|-------|--------|---------|
| Мотивация | Мотивация | кнопка Excel |
| Оборачиваемость | Оборачиваемость | Excel (матрица) |
| План/факт | Квартальные планы | Excel |
| Справочники | Номенклатура / Контрагенты | Excel (по фильтру, до `EXPORT_MAX_ROWS`) |

## Email / рассылка

Админ → вкладка **Рассылка**: состав письма, SMTP, получатели. Без SMTP письмо не уходит — только превью. Авторассылка пн 08:00, если включена.

## Rate limit

- Login: `RATE_LIMIT_LOGIN_PER_MINUTE` (по умолчанию 10/мин на IP)
- API: `RATE_LIMIT_API_PER_MINUTE` (по умолчанию 180/мин на IP)

Ответ при превышении: HTTP 429.

## Типовые проблемы

| Симптом | Что проверить |
|---------|----------------|
| OData warn/fail | URL/учётка в админке, SSL, права OData в 1С |
| Пустые отчёты | `is_promo`, Excel продажи/остатки, период |
| Frontend не обновляется | `docker compose restart frontend` + Ctrl+F5 |
| Postgres на :5432 занят | не путать host Postgres с контейнерным |

## Секреты

Не коммитить: `.env`, `1c.txt`, `docs/odata-metadata.xml`.

Пользовательские гайды: [guides/README.md](guides/README.md).
