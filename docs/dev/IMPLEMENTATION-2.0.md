# INTERNAL: Реализация SPEC-2.0 (Account-Based Chat)

**Статус:** ✅ Завершено (4 Февраля 2026)

**Коммиттер:** Главный Архитектор

---

## ИЗМЕНЕНИЯ

### 1. ✅ Бэкенд: Модели БД (main.py)

```python
# Organization model
class Organization(Base):
    __tablename__ = "organizations"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    inn = Column(String, nullable=True, index=True)
    is_vip = Column(Boolean, default=False)
    contacts = relationship("Contact", back_populates="org")

# Contact model с связью на Organization
class Contact(Base):
    __tablename__ = "contacts"
    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    name = Column(String, index=True)
    position = Column(String, nullable=True)
    email = Column(String, index=True, unique=True, nullable=True)
    telegram_id = Column(String, index=True, unique=True, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    org = relationship("Organization", back_populates="contacts")
```

### 2. ✅ API: GET /api/chats (Иерархический формат)

**Ответ:**
```json
{
  "unsorted": [
    {
      "chat_id": "email_unknown@company.com",
      "source": "email",
      "display_name": "Unknown User",
      "last_message": "Здравствуйте...",
      "last_activity_ts": 1700000000,
      "unread": 1
    }
  ],
  "groups": [
    {
      "org_id": 1,
      "org_name": "ПАО Газпром",
      "is_vip": true,
      "total_unread": 5,
      "last_activity_ts": 1700100000,
      "contacts": [
        {
          "chat_id": "email_ivanov@gazprom.ru",
          "source": "email",
          "display_name": "Иванов И.И.",
          "position": "Нач. закупки",
          "sender_id": "ivanov@gazprom.ru",
          "last_message": "Готово",
          "last_activity_ts": 1700100000,
          "unread": 2
        }
      ]
    }
  ]
}
```

**Алгоритм:**
1. Получить все сообщения, сгруппировать по `sender_id`
2. Для каждого `sender_id` найти контакт по email или telegram_id
3. Если контакт найден + есть `org_id` → добавить в группу Организации
4. Иначе → добавить в `unsorted`
5. Сортировка: группы по `last_activity_ts`, контакты внутри групп по активности

### 3. ✅ API: POST /api/contacts (Создание контакта + Organization)

**Input:**
```json
{
  "sender_id": "tg_12345",
  "name": "Петров И.И.",
  "position": "Менеджер",
  "source": "telegram",
  "org_mode": "new",
  "new_org_name": "ООО Новая Компания",
  "inn": "7708001541"
}
```

**Поддерживаемые режимы:**
- `org_mode: null` → Контакт без организации
- `org_mode: "existing"` → Привязка к существующей (требует `org_id`)
- `org_mode: "new"` → Создание новой организации на лету (требует `new_org_name`)

**Output:**
```json
{
  "status": "ok",
  "contact": {
    "id": 42,
    "name": "Петров И.И.",
    "position": "Менеджер",
    "org_id": 5,
    "email": null,
    "telegram_id": "tg_12345",
    "created_at": "2026-02-04T10:30:00"
  }
}
```

### 4. ✅ Фронтенд: Master-Detail Layout (App.vue)

**Адаптивность (Tailwind + Vue):**

| Состояние | Desktop (>768px) | Mobile (<768px) |
|-----------|-----------------|-----------------|
| Чат не выбран | Сайдбар видна (w-96), справа пусто | На весь экран сайдбар |
| Чат выбран | Сайдбар видна, справа чат | На весь экран чат (fixed z-50) |

**Компоненты:**

1. **Сайдбар (Accordion):**
   - Секция "Неразобранное" (всегда разернута)
   - Группы организаций (коллапсируются по клику)
   - При свернутой группе показываем бейдж с суммой непрочитанных
   - Цветовые значки: синий (TG), красный (Email)

2. **Chat Header:**
   - Имя контакта (слева)
   - Название организации (кликабельное, открывает модалку)
   - Кнопка "Привязать" (если контакт неизвестен)
   - Кнопка "⋮" (мобильное меню)

3. **Модалка "Привязать контакт":**
   - Поле "ФИО" (readonly, из сообщения)
   - Поле "Должность" (editable)
   - Радио-кнопки: "Выбрать существующую" / "Создать новую"
   - Условные поля (dropdown или текстовые поля для новой org)

4. **Модалка "О компании":**
   - Название + VIP статус
   - ID, кол-во контактов, непрочитанные
   - Список всех контактов этой организации (с должностями)

---

## TESTING CHECKLIST

### Backend Tests

```bash
# 1. Проверить иерархию GET /api/chats
curl http://localhost:8000/api/chats | jq

# Expected: 
# - unsorted[] содержит контакты БЕЗ org_id
# - groups[] содержит организации с их контактами
# - Сортировка по last_activity_ts

# 2. Создать организацию на лету
curl -X POST http://localhost:8000/api/contacts \
  -H "Content-Type: application/json" \
  -d '{
    "sender_id": "test@example.com",
    "name": "Test User",
    "position": "Engineer",
    "source": "email",
    "org_mode": "new",
    "new_org_name": "Test Company Inc.",
    "inn": "1234567890"
  }' | jq

# Expected: status: "ok", org_id не null

# 3. Привязать к существующей организации
curl -X POST http://localhost:8000/api/contacts \
  -H "Content-Type: application/json" \
  -d '{
    "sender_id": "another@test.com",
    "name": "Another User",
    "position": "Manager",
    "source": "email",
    "org_mode": "existing",
    "org_id": 1
  }' | jq

# Expected: status: "ok"

# 4. Проверить ошибки
# - duplicate email → "already exists"
# - org_mode="existing" без org_id → error
# - org_mode="new" без new_org_name → error
```

### Frontend Tests

1. **Адаптивность:**
   - Открыть на Desktop (>768px) → Сайдбар слева, чат справа
   - Открыть на Mobile (<768px) → Только сайдбар, при клике на чат → только чат
   - Кнопка "Назад" видна только на мобильном

2. **Аккордеон:**
   - Группа "Неразобранное" всегда видна
   - При клике на заголовок группы → раскрывается/сворачивается
   - Бейдж с числом непрочитанных видна только когда группа свернута

3. **Привязка контакта:**
   - Кнопка "Привязать" видна только для неизвестных контактов
   - Выбор org_mode → отображаются нужные поля
   - После создания → чат перемещается в нужную группу
   - Страница перезагружается данные по /api/chats

4. **Модалка компании:**
   - Клик на название организации в header чата → открывается модалка
   - Показываются все контакты этой организации

---

## DEPLOYMENT NOTES

### Database Migration

```sql
-- Если таблицы уже созданы, просто убедитесь что есть foreign key:
ALTER TABLE contacts 
  ADD CONSTRAINT fk_contacts_org 
  FOREIGN KEY (org_id) REFERENCES organizations(id) ON DELETE SET NULL;

-- Индексы (уже созданы через SQLAlchemy):
-- - organizations.name (UNIQUE)
-- - organizations.inn
-- - contacts.email (UNIQUE)
-- - contacts.telegram_id (UNIQUE)
-- - contacts.org_id
```

### Docker Compose

Убедитесь что переменные окружения установлены:
```env
DATABASE_URL=postgresql://anaconda_user:***REMOVED***@db:5432/anaconda_db
TELEGRAM_BOT_TOKEN=...
EMAIL_IMAP_USER=...
EMAIL_IMAP_PASSWORD=...
```

### CI/CD Pipeline

При следующем пуше Git:
1. Автотесты (pytest для API)
2. Линтеры (flake8, eslint для Vue)
3. Build Docker images
4. Deploy на staging (docker-compose)
5. Smoke tests

---

## KNOWN LIMITATIONS & FUTURE

1. **Message History:** История сообщений не отображается (заглушка в чате)
   - Нужно добавить query последних 50 сообщений для selected_chat.sender_id

2. **Alembic Migrations:** Используется `Base.metadata.create_all()`, нужна история миграций
   - `alembic init alembic && alembic revision --autogenerate`

3. **Real-time Updates:** Polling каждые 5 сек, нужны WebSockets
   - FastAPI + python-socketio для настоящего real-time

4. **Organization Details:** Нет полей (адрес, реквизиты, INN проверка)
   - Добавить валидацию ИНН через DADATA API (когда будет доступ)

---

## CONTACT

**Главный Архитектор:** GitHub Copilot (Claude Haiku 4.5)

**Дата:** 4 Февраля 2026

**Version:** SPEC-2.0 Final
