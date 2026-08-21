# Настройка Anaconda MVP

## Переменные окружения

Создайте локальный файл, который исключён из Git:

```bash
./CREATE_ENV.sh
```

Заполните все placeholders в `.env`. Используйте отдельные credentials для
production; не копируйте значения из документации или Git history.

Обязательные группы переменных:

- PostgreSQL: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`,
  `DATABASE_URL`;
- Telegram: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_USERNAME`,
  `TELEGRAM_WEBHOOK_URL`, `TELEGRAM_USE_POLLING`;
- IMAP: `EMAIL_IMAP_HOST`, `EMAIL_IMAP_PORT`, `EMAIL_IMAP_USER`,
  `EMAIL_IMAP_PASSWORD`, `EMAIL_IMAP_SSL`;
- public URLs: `API_URL`, `FRONTEND_URL`.

Для Docker Compose hostname PostgreSQL в `DATABASE_URL` — `db`. Для
Kubernetes Secret значение `DATABASE_URL` не импортируется: deployment
формирует его из `POSTGRES_PASSWORD` и Service `anaconda-postgres`.

## Проверка

После запуска:

```bash
curl -fsS http://localhost:8000/live
curl -fsS http://localhost:8000/ready
```

Настройку Telegram webhook выполняйте только через HTTPS endpoint и только
после ротации credentials, если прежние значения когда-либо попадали в Git.

## Безопасность

- `.env` должен иметь mode `0600` и не должен попадать в Git.
- Не логируйте token/password и не публикуйте их в issue, CI logs или docs.
- Любой credential, обнаруженный в Git history, считается скомпрометированным
  и подлежит ротации.
