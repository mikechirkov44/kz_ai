# Вторая база 1С

Подключается **в конце** проекта. Каркас уже есть:

1. В админке → «Подключения 1С» заполнить URL / логин / пароль для `miamor`.
2. Включить чекбокс «Включено».
3. «Проверить связь» → «Полный sync» с `source_id=miamor`.

Либо через `.env` (сиды при старте, если строки в БД ещё нет):

```
ODATA_MIAMOR_URL=https://.../odata/standard.odata/
ODATA_MIAMOR_USER=...
ODATA_MIAMOR_PASSWORD=...
ODATA_MIAMOR_VERIFY_SSL=false
```

После появления строки в БД приоритет у админ-настроек (не `.env`).

В UI контрагенты фильтруются по `source_id` (`/api/v1/counterparties?source_id=miamor`).
