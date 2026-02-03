#!/bin/bash
# Скрипт для создания .env файла

if [ -f .env ]; then
    echo "Файл .env уже существует!"
    read -p "Перезаписать? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

cat > .env << 'ENVEOF'
# Конфигурация Anaconda MVP

# База данных PostgreSQL
POSTGRES_USER=anaconda_user
POSTGRES_PASSWORD=***REMOVED***
POSTGRES_DB=anaconda_db
DATABASE_URL=postgresql://anaconda_user:***REMOVED***@db:5432/anaconda_db

# Telegram Bot API
TELEGRAM_BOT_TOKEN=***REMOVED***
TELEGRAM_BOT_USERNAME=anaconda_mvp_bot
TELEGRAM_WEBHOOK_URL=http://31.59.106.120:8000/api/webhook/telegram

# Почта Яндекс (IMAP)
EMAIL_IMAP_HOST=imap.yandex.ru
EMAIL_IMAP_PORT=993
EMAIL_IMAP_USER=***REMOVED***
EMAIL_IMAP_PASSWORD=***REMOVED***
EMAIL_IMAP_SSL=true

# Настройки приложения
API_URL=http://31.59.106.120:8000/api
FRONTEND_URL=http://31.59.106.120
ENVEOF

echo "✅ Файл .env создан!"
echo "⚠️  Не забудьте отредактировать .env и заполнить реальные данные для почты!"
