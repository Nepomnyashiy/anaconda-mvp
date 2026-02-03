# Инструкция по настройке Anaconda MVP

## Настройка переменных окружения

1. **Создайте файл `.env` на основе примера:**
```bash
cp env.example .env
```

2. **Отредактируйте `.env` файл и заполните реальными данными:**

### База данных PostgreSQL
```env
POSTGRES_USER=anaconda_user
POSTGRES_PASSWORD=***REMOVED***  # Измените на безопасный пароль
POSTGRES_DB=anaconda_db
DATABASE_URL=postgresql://anaconda_user:***REMOVED***@db:5432/anaconda_db
```

### Telegram Bot API
```env
TELEGRAM_BOT_TOKEN=***REMOVED***
TELEGRAM_BOT_USERNAME=anaconda_mvp_bot
TELEGRAM_WEBHOOK_URL=http://31.59.106.120:8000/api/webhook/telegram
```

**Важно:** Замените `31.59.106.120` на IP вашего сервера или домен.

### Почта Яндекс (IMAP)
```env
EMAIL_IMAP_HOST=imap.yandex.ru
EMAIL_IMAP_PORT=993
EMAIL_IMAP_USER=***REMOVED***
EMAIL_IMAP_PASSWORD=***REMOVED***
EMAIL_IMAP_SSL=true
```

### Настройки приложения
```env
API_URL=http://31.59.106.120:8000/api
FRONTEND_URL=http://31.59.106.120
```

## Настройка Telegram бота

После запуска приложения настройте webhook для Telegram бота:

```bash
curl http://localhost:8000/api/telegram/setup
```

Или откройте в браузере:
```
http://localhost:8000/api/telegram/setup
```

## Проверка работы

1. **Проверка Telegram:**
   - Отправьте сообщение боту `@anaconda_mvp_bot`
   - Сообщение должно появиться в ленте на фронтенде

2. **Проверка почты:**
   - Отправьте тестовое письмо на настроенный email
   - Или вручную запустите проверку:
   ```bash
   curl -X POST http://localhost:8000/api/email/check
   ```

3. **Проверка ленты:**
   - Откройте `http://localhost` (или IP вашего сервера)
   - Должны отображаться сообщения из Telegram и почты

## Безопасность

⚠️ **Важно:** Файл `.env` содержит секретные данные и не должен попадать в систему контроля версий (Git).

Файл `.env` уже добавлен в `.gitignore`.
