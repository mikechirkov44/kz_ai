# Runbook — Jewelry AI Analytics

Операционные шаги для локального/staging/prod окружения.

## Подъём (dev)

```bash
docker compose up -d --build
```

Сервисы: API `:8000`, frontend `:5173`, PostgreSQL, Redis, Celery worker/beat.

Health: `GET http://localhost:8000/api/v1/admin/health` (нужен JWT admin) или смотреть OpenAPI `/docs`.

Логин по умолчанию (dev): `admin@example.com` / из `.env` (`ADMIN_PASSWORD`).

## Prod минимум

```bash
cp .env.example .env.prod   # задать SECRET_KEY, POSTGRES_PASSWORD, OData, SMTP, CORS
# положить TLS: deploy/certs/fullchain.pem + privkey.pem
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

- HTTPS через `deploy/nginx.conf`
- Без bind-mount исходников, `APP_ENV=production`, `SYNC_ENABLED=true`
- Пароль пользователя: смена каждые `PASSWORD_MAX_AGE_DAYS` (по умолчанию 90)

### Чеклист перед боем

- [ ] Нет дефолтных паролей в `.env.prod`
- [ ] CORS только на прод-домен
- [ ] OData URL/учётки проверены (`test` в админке) для всех баз
- [ ] Бэкап cron: `scripts/backup_postgres.sh` (см. `docs/backup-restore.md`)
- [ ] Health мониторинг / алерт при fail sync
- [ ] Digest SMTP проверен preview + тестовая отправка

## OData / sync

1. Админ → **Подключения 1С**: имя, URL, логин, пароль, «Проверить связь».
2. **Обновить данные** или **Полная синхронизация** по выбранной базе или всем включённым.
3. Участников акции отметить `is_promo` (если не пришло из 1С).

Несколько баз: см. `docs/second-base.md`.

Расписание Celery: инкремент каждые 15 мин, полный sync 02:00, digest пн 08:00 (Asia/Almaty).

## Excel-загрузки

1. Данные → Загрузка Excel.
2. Скачать шаблон нужного типа.
3. **Предпросмотр** (валидация без записи) → затем **Загрузить**; при ошибках — `errors.xlsx`.

Типы: продажи, остатки, both, доп. мотивация.

## Отчёты

| Отчёт | Экран | Экспорт |
|-------|--------|---------|
| Мотивация | Мотивация | кнопка Excel |
| Оборачиваемость | Оборачиваемость | Excel (матрица); опция «средние остатки» |
| План/факт | Квартальные планы | Excel |
| Справочники | Номенклатура / Контрагенты | Excel (по фильтру, до `EXPORT_MAX_ROWS`) |

Рег. директор с заполненным `region` видит только контрагентов своего региона.

## Email / рассылка

Админ → вкладка **Рассылка**: состав письма, SMTP, получатели. В превью есть срез **по менеджерам**. Без SMTP письмо не уходит — только превью. Авторассылка пн 08:00, если включена.

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
| Редирект на смену пароля | `PASSWORD_MAX_AGE_DAYS`, поле `password_changed_at` |

## Секреты

Не коммитить: `.env`, `.env.prod`, `1c.txt`, `docs/odata-metadata.xml`, `deploy/certs/*`.

Пользовательские гайды: [guides/README.md](guides/README.md).
