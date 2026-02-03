# 🐍 Anaconda MVP 1.0

Корпоративная платформа для единого окна продаж.

## Архитектура

- **anaconda-api**: FastAPI + PostgreSQL 16
- **anaconda-web**: Vue.js 3 + Vite
- **База данных**: PostgreSQL 16 (с персистентным хранилищем)
- **Развертывание**: Docker Compose

## Быстрый старт

### Требования

- Docker и Docker Compose
- Доступ к серверу (Ubuntu 24.04)
- Токен Telegram бота
- Данные для доступа к почте (IMAP)

### Настройка

1. **Создайте файл `.env` с настройками:**
```bash
cp env.example .env
# Отредактируйте .env и заполните реальными данными
```

Подробная инструкция в файле [SETUP.md](SETUP.md)

### Развертывание

1. **Очистка (если были старые контейнеры):**
```bash
cd ~/kip-service
docker compose down -v
```

2. **Запуск всех сервисов:**
```bash
docker compose up -d --build
```

3. **Настройка Telegram webhook:**
```bash
curl http://localhost:8000/api/telegram/setup
```

3. **Проверка статуса:**
```bash
docker compose ps
```

4. **Просмотр логов:**
```bash
docker compose logs -f
```

## Доступ к сервисам

### Локальный запуск:
- **anaconda-web**: http://localhost (порт 80)
- **anaconda-api**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health
- **PostgreSQL**: localhost:5433 (внешний порт, внутри контейнера 5432)

### На сервере (31.59.106.120):
- **anaconda-web**: http://31.59.106.120 (порт 80)
- **anaconda-api**: http://31.59.106.120:8000
- **API Docs**: http://31.59.106.120:8000/docs
- **Health Check**: http://31.59.106.120:8000/health

## API Endpoints (Точки входа API)

### Сообщения
- `GET /api/messages` - Получить последние 50 сообщений

### Лиды
- `POST /api/leads` - Создать новый лид
  ```json
  {
    "name": "Имя клиента",
    "source": "telegram"
  }
  ```

### Webhooks (Вебхуки)
- `POST /api/webhook/telegram` - Вебхук для приема сообщений из Telegram
- `GET /api/telegram/setup` - Настройка webhook для Telegram бота

### Почта
- `POST /api/email/check` - Ручная проверка почты (для тестирования)

## Структура проекта

```
anaconda/
├── docker-compose.yml      # Конфигурация всех сервисов
├── .env                    # Переменные окружения (в .gitignore)
├── env.example             # Пример конфигурации
├── anaconda_api/           # FastAPI сервер (основной бэкенд)
│   ├── main.py             # Точка входа приложения
│   ├── requirements.txt     # Зависимости Python
│   └── Dockerfile          # Контейнеризация API
├── anaconda_web/           # Vue.js фронтенд
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   ├── Dockerfile
│   └── src/
│       ├── App.vue         # Главный компонент
│       └── main.js         # Точка входа
└── docs/                   # Документация проекта
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── main.py            # FastAPI приложение
└── frontend/
    ├── Dockerfile
    ├── package.json
    ├── vite.config.js
    ├── index.html
    └── src/
        ├── main.js
        └── App.vue        # Vue компонент
```

## Проверка работоспособности

1. Откройте `http://localhost` (локально) или `http://31.59.106.120` (на сервере) - должна открыться лента сообщений
2. Отправьте тестовый вебхук:
```bash
curl -X POST http://31.59.106.120:8000/api/webhook/max \
  -H "Content-Type: application/json" \
  -d '{"text": "Тестовое сообщение", "sender": {"name": "Тест"}}'
```
3. Нажмите "+ В Лиды" на любом сообщении
4. Перезапустите контейнеры: `docker compose restart`
5. Обновите страницу - **сообщения должны остаться** (данные в БД)
anaconda-api
## Управление

### Остановка
```bash
docker compose down
```

### Перезапуск
```bash
docker compose restart
```

### Просмотр логов конкретного сервиса
```bash
docker compose logs -f backend
docker compose logs -f anaconda-web
docker compose logs -f db
```

### Подключение к БД
```bash
docker compose exec db psql -U anaconda_user -d anaconda_db
```

## Данные

Все данные сохраняются в Docker volume `postgres_data` и не теряются при перезапуске контейнеров.

## Возможности MVP 1.0

✅ Сохранение сообщений в PostgreSQL  
✅ Создание лидов из сообщений  
✅ Вебхук для приема сообщений  
✅ Лента сообщений с автообновлением  
✅ Персистентное хранилище данных  

---

**Статус**: MVP 1.0 готов к демонстрации
