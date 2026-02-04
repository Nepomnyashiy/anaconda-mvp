# IMPLEMENTATION-004: Anaconda Core v4.0

## 📋 Обзор реализации

Данный документ описывает реализацию SPEC-004 "Anaconda Core v4.0" — единое досье контакта с агрегацией каналов.

**Дата реализации:** 04.02.2026  
**Статус:** ✅ Завершено

---

## 🔄 Изменения в Backend (anaconda_api/main.py)

### 1. Обновление модели Message

Добавлены новые поля для поддержки исходящих сообщений и статуса прочтения:

```python
class Message(Base):
    # ... существующие поля ...
    is_outbound = Column(Boolean, default=False)  # True = мы отправили
    is_read = Column(Boolean, default=False)      # Статус прочтения
    attachment_path = Column(String, nullable=True)  # Путь к файлу вложения
```

### 2. Новые API Endpoints

#### GET /api/hub_structure
Возвращает полное дерево для левого меню согласно SPEC-004.

**Ответ:**
```json
{
  "unsorted": [
    {"sender_id": "123456", "source": "telegram", "preview": "Текст...", "time": "14:15", "display_name": "User"}
  ],
  "organizations": [
    {
      "id": 1,
      "name": "ПАО Газпром",
      "is_vip": true,
      "contacts": [
        {"id": 10, "name": "Иванов Иван", "position": "Директор", "channels": ["telegram", "email"], "unread_count": 2}
      ]
    }
  ]
}
```

#### GET /api/history/{contact_id}
Агрегирует историю сообщений из всех каналов контакта.

**Ответ:**
```json
{
  "contact": {
    "id": 10,
    "name": "Иванов Иван",
    "position": "Директор",
    "email": "ivanov@gazprom.ru",
    "telegram_id": "123456",
    "organization": {"id": 1, "name": "ПАО Газпром", "is_vip": true}
  },
  "messages": [
    {
      "id": 1,
      "source": "telegram",
      "text": "Привет!",
      "is_outbound": false,
      "is_read": true,
      "created_at": "2026-02-04T10:30:00"
    }
  ]
}
```

#### POST /api/send
Единый метод отправки сообщений в Telegram или Email.

**Запрос:**
```json
{
  "contact_id": 10,
  "channel": "telegram",
  "text": "Привет!"
}
```

**Логика:**
1. Находит контакт по ID
2. Если канал "telegram" — отправляет через Telegram Bot API
3. Если канал "email" — отправляет через SMTP (Яндекс.Почта, порт 465)
4. Сохраняет сообщение в БД с `is_outbound=True`

#### POST /api/link_contact
Превращает "Неразобранное" в привязанного контакта.

**Запрос:**
```json
{
  "sender_id": "123456",
  "name": "Петр Иванов",
  "position": "Менеджер",
  "org_id": 1
}
```

**Эффект:** Чат перемещается из "Неразобранного" в папку организации.

---

## 🎨 Изменения в Frontend (anaconda_web/src/App.vue)

### 1. История сообщений

- Загрузка истории через `/api/history/{contact_id}`
- Визуальное разделение по источникам:
  - 🔵 Telegram — синяя полоска слева
  - 🔴 Email — красная полоска слева
  - ✅ Исходящие — зеленый фон, выравнивание справа

### 2. Селектор канала отправки

- Кнопки выбора канала над полем ввода
- Активны только доступные каналы контакта
- Визуальное выделение выбранного канала

### 3. Модалка привязки контакта

- Форма с полями: ФИО, Должность
- Выбор организации из списка
- Информация об источнике (Telegram/Email + ID)
- Вызов `/api/link_contact` при сохранении

---

## 📁 Измененные файлы

| Файл | Изменения |
|------|-----------|
| `anaconda_api/main.py` | Новые поля Message, 4 новых endpoint'а |
| `anaconda_web/src/App.vue` | История чата, селектор канала, привязка контакта |
| `docs/dev/IMPLEMENTATION-004.md` | Документация (этот файл) |

---

## ✅ Критерий успеха (тестирование)

Сценарий по SPEC-004:

1. ✅ Открыть "Неразобранное" — видим "User123"
2. ✅ Нажать "Привязать" — выбрать "Петр из Газпрома"
3. ✅ Чат перемещается в папку "Газпром"
4. ✅ Открыть Петра — видим историю сообщений
5. ✅ Написать "Привет" — выбрать канал Telegram
6. ✅ Петр получает сообщение в Telegram
7. ✅ Ответ Петра появляется в той же ленте

---

## 🔧 Конфигурация

### Переменные окружения для отправки

```env
# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token

# Email SMTP (для отправки)
EMAIL_SMTP_HOST=smtp.yandex.ru
EMAIL_SMTP_PORT=465
EMAIL_SMTP_USER=your_email@yandex.ru
EMAIL_SMTP_PASSWORD=your_app_password

# Email IMAP (для получения)
EMAIL_IMAP_HOST=imap.yandex.ru
EMAIL_IMAP_PORT=993
EMAIL_IMAP_USER=your_email@yandex.ru
EMAIL_IMAP_PASSWORD=your_app_password
```

---

## 🚀 Развертывание

```bash
# Пересобрать контейнеры
docker-compose down
docker-compose up -d --build

# Проверить логи
docker-compose logs -f anaconda_api
```

---

## 📊 API Summary

| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/api/hub_structure` | Дерево контактов для меню |
| GET | `/api/history/{contact_id}` | История сообщений контакта |
| POST | `/api/send` | Отправка сообщения |
| POST | `/api/link_contact` | Привязка неразобранного к организации |
| GET | `/api/chats` | Legacy endpoint (совместимость) |
| GET | `/api/organizations` | Список организаций |
| POST | `/api/contacts` | Создание контакта |

---

## 🔮 TODO (следующие итерации)

- [ ] Загрузка файлов (attachment_path)
- [ ] Редактирование контакта (добавление второго канала)
- [ ] Bulk-операции с неразобранными
- [ ] Поиск по истории сообщений
- [ ] Шаблоны быстрых ответов
