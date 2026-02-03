# Интеграция сообщений (Telegram + Email IMAP)

## 🟢 Статус
✓ **Telegram polling активен** - Бот получает сообщения методом long polling  
✓ **Email IMAP polling активен** - Письма получаются из Яндекс.Почты

## Как это работает

### Telegram
1. API запускает фоновый worker при старте
2. Worker постоянно опрашивает Telegram Bot API методом `getUpdates` (каждые 30 сек)
3. Когда новое сообщение приходит в бота, оно сохраняется в БД
4. Фронтенд получает сообщения из API каждые 2 секунды

### Email (IMAP)
1. API запускает фоновый IMAP worker при старте
2. Worker подключается к Яндекс.Почте каждые 60 сек
3. Получает последние 10 писем из папки INBOX
4. Парсит отправителя, тему и текст письма
5. Сохраняет в БД с source="email"
6. Фронтенд отображает письма вместе с сообщениями

## Используемые ботов и сервисов

### Telegram
- **Бот**: @anaconda_mvp_bot (ID: 8582672980)
- **Метод**: Long polling (getUpdates)
- **Интервал опроса**: 30 секунд

### Email (IMAP)
- **Сервер**: imap.yandex.ru:993 (SSL)
- **Аккаунт**: ***REMOVED***
- **Интервал проверки**: 60 секунд
- **Кодировка**: Автоматическое декодирование UTF-8 и base64

## Как отправить сообщение

### В Telegram
1. Откройте Telegram
2. Найдите бота **@anaconda_mvp_bot**
3. Отправьте любое сообщение
4. Сообщение появится в интерфейсе за 5-60 секунд

### На Email
1. Отправьте письмо на *****REMOVED*****
2. Письмо появится в интерфейсе за 5-120 секунд (зависит от задержки проверки)

## Примеры запросов

```bash
# Проверить здоровье API и статус polling'ов
curl http://localhost:8000/health | jq

# Получить все сообщения (последние 50)
curl http://localhost:8000/api/messages | jq

# Информация о Telegram боте
curl http://localhost:8000/api/telegram/info | jq

# Информация о Email IMAP polling'е
curl http://localhost:8000/api/email/info | jq
```

## Логирование

Все действия логируются в контейнер:

```bash
# Live логи
docker compose logs anaconda-api -f

# Только успешные Telegram сообщения
docker compose logs anaconda-api | grep "Telegram message saved"

# Только успешные Email письма
docker compose logs anaconda-api | grep "Email saved"

# Ошибки
docker compose logs anaconda-api | grep -i "error"
```

## Пример логов при старте

```
INFO:main:✓ Telegram polling started
INFO:main:✓ Telegram polling thread started
INFO:main:✓ Email IMAP polling started
INFO:main:✓ Email IMAP polling thread started
```

## Техническая информация

### Endpoints
- `GET /health` - Статус API, DB, и всех polling'ов
- `GET /api/messages` - Все сообщения (последние 50)
- `GET /api/telegram/info` - Информация о Telegram боте
- `GET /api/email/info` - Информация о Email IMAP
- `POST /api/webhook/telegram` - Webhook (для совместимости)
- `POST /api/webhook/max` - Webhook для Max CRM

### Структура Message в БД
```sql
CREATE TABLE messages (
    id SERIAL PRIMARY KEY,
    source VARCHAR (telegram, email, max),
    sender VARCHAR,
    text TEXT,
    created_at TIMESTAMP
);
```

## Если сообщения не приходят

### Telegram
1. Проверьте статус:
   ```bash
   curl http://localhost:8000/health | jq '.telegram_polling'
   # Должно быть: true
   ```

2. Проверьте логи:
   ```bash
   docker compose logs anaconda-api | tail -50
   ```

3. Убедитесь, что бот запущен:
   ```bash
   curl http://localhost:8000/api/telegram/info | jq '.bot'
   ```

### Email
1. Проверьте статус:
   ```bash
   curl http://localhost:8000/health | jq '.email_polling'
   # Должно быть: true
   ```

2. Проверьте учетные данные в .env:
   ```bash
   cat .env | grep EMAIL_IMAP
   ```

3. Проверьте логи на ошибки IMAP:
   ```bash
   docker compose logs anaconda-api | grep "IMAP"
   ```

4. Проверьте, что почта доступна (если используется двухфакторная аутентификация, нужен пароль приложения)

## Примечания

- **Webhook требует HTTPS** с действительным сертификатом (используется polling вместо webhook)
- **Polling работает локально** и в любой среде (более надежно)
- **Максимум 1 поток polling'а** на одного бота/аккаунта
- **Кодировка писем** автоматически преобразуется из UTF-8, Base64 и других форматов
- **Последние 10 писем** проверяются каждые 60 секунд (можно изменить интервал)

## Используемые технологии
- **Telegram Bot API** - https://core.telegram.org/bots/api
- **IMAP RFC 3501** - Standard for email retrieval
- **Long Polling** - Стандартный метод получения обновлений
- **SQLAlchemy** - ORM для PostgreSQL
- **FastAPI** - Веб-фреймворк

