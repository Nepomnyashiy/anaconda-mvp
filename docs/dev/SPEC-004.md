ТЕХНИЧЕСКАЯ СПЕЦИФИКАЦИЯ: ANACONDA CORE (v4.0)
Принцип: единое досье контакта + агрегация каналов. Стек: Python 3.11 (FastAPI), SQLite/PostgreSQL, Vue.js 3, polling workers.

---

## 1. ДАННЫЕ И МИГРАЦИИ (ИСТОЧНИК ПРАВДЫ)

Цель: Contact остаётся единой точкой входа, а любые сообщения и каналы однозначно сопоставляются с этим контактом. Все схемы ниже обязательны для Alembic/SQL миграций.

### 1.1 ER-диаграмма (словесно)
```
organizations 1<--n contacts 1<--n messages
                         └----< contact_channels (future ready)
```

### 1.2 Таблица `organizations`
| Колонка | Тип | Ограничения | Комментарий |
| --- | --- | --- | --- |
| `id` | SERIAL / INTEGER | PK | |
| `name` | VARCHAR(255) | UNIQUE NOT NULL, INDEX | Отображаемый заголовок папки |
| `is_vip` | BOOLEAN | DEFAULT FALSE | Флаг для сортировки и визуального выделения |
| `created_at/updated_at` | TIMESTAMP | DEFAULT now() | Для аудита |

Индексы: `idx_org_name_lower` (LOWER(name)) для поиска, `idx_org_is_vip` для сортировки.

### 1.3 Таблица `contacts`
| Колонка | Тип | Ограничения | Комментарий |
| --- | --- | --- | --- |
| `id` | SERIAL | PK | |
| `org_id` | INTEGER | FK → organizations(id) ON DELETE SET NULL | Контакт может быть без организации до классификации |
| `name` | VARCHAR(255) | NOT NULL | Главный label |
| `position` | VARCHAR(255) | NULL | Показываем в header |
| `email` | VARCHAR(320) | UNIQUE NULL, INDEX | LOWER(email) UNIQUE KEY для предотвращения дублей |
| `telegram_id` | VARCHAR(64) | UNIQUE NULL, INDEX | Идентификатор чата/пользователя |
| `phone` | VARCHAR(32) | UNIQUE NULL, INDEX | Зарезервировано |
| `created_at/updated_at` | TIMESTAMP | DEFAULT now() | |
| `archived_at` | TIMESTAMP | NULL | Soft-delete (контакт скрывается, но история хранится) |

Комбинированные индексы: `(org_id, is_vip)` через join с organizations для быстрого построения дерева.

### 1.4 Таблица `messages`
| Колонка | Тип | Ограничения | Комментарий |
| --- | --- | --- | --- |
| `id` | SERIAL | PK | |
| `contact_id` | INTEGER | FK → contacts(id) ON DELETE SET NULL | NULL для “Неразобранного” |
| `source` | ENUM('telegram','email') | NOT NULL, INDEX | Канал |
| `sender_id` | VARCHAR(255) | NOT NULL, INDEX | Технический ID (chat_id/email) |
| `is_outbound` | BOOLEAN | DEFAULT FALSE | Мы отправили |
| `is_read` | BOOLEAN | DEFAULT FALSE | Для расчёта badge |
| `text` | TEXT | NULL | Тело |
| `attachment_path` | VARCHAR(512) | NULL | Храним относительный путь |
| `created_at` | TIMESTAMP | DEFAULT now(), INDEX | Сортировка |
| `updated_at` | TIMESTAMP | DEFAULT now() | |

Индексы: `idx_messages_contact_created_at`, `idx_messages_sender_source`, `idx_messages_unread` (WHERE is_read=false). Уникальность на уровне `(source, external_message_id)` — хранится в служебной колонке `external_id` (добавить при первой миграции) для защиты от дублей.

### 1.5 Папка «Неразобранное»
Определение: `messages` с `contact_id IS NULL`. Критерии выхода — успешный `POST /api/link_contact` или ручное привязывание через UI, что обновляет `messages.contact_id` массово (`UPDATE ... WHERE sender_id = :matched_id`).

### 1.6 Миграции
- Обязательное использование Alembic (репо: `anaconda_api/alembic`).
- Каждая новая колонка/индекс описывается в SPEC с примером `ALTER TABLE`.
- Базовая миграция для BUGFIX-004:
```sql
ALTER TABLE messages
  ADD COLUMN IF NOT EXISTS is_outbound BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS is_read BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS attachment_path VARCHAR(512);
```
- Миграция на `contact_id` (nullable) и индекс на `sender_id`.
- Checklist для релиза:
  1. `alembic revision --autogenerate -m "spec004"`
  2. Верификация SQL (включая ENUM создание)
  3. `alembic upgrade head`
  4. Smoke-тест `/api/hub_structure`

---

## 2. WORKERS И ИНТЕГРАЦИИ

### 2.1 Общие требования
- Покрываем Telegram Polling Bot и Email IMAP Poller.
- Частота polling: каждые 5 секунд Telegram, каждые 15 секунд Email (configurable: `TELEGRAM_POLL_INTERVAL`, `EMAIL_POLL_INTERVAL`).
- Все операции логируются в structured JSON в `stdout` и сохраняются в Loki/ELK (формат: `timestamp, worker, source, sender_id, event, status`).
- Ретраи: 3 попытки с экспоненциальной задержкой (1s, 5s, 30s). После 3-х — сообщение в DLQ (PostgreSQL таблица `worker_failures`).
- Дедупликация: хранить `external_id` (Telegram `update_id`, Email `Message-ID`). Вставка с `ON CONFLICT DO NOTHING`.
- Безопасность: токены в secrets (`TELEGRAM_BOT_TOKEN`, `EMAIL_SMTP_PASSWORD`, `EMAIL_IMAP_PASSWORD`). Работники запускаются в private network, IP whitelisting на SMTP/IMAP.

### 2.2 Pipeline Telegram
1. Poll `getUpdates` with offset.
2. Нормализуем payload → `{external_id, sender_id, text, attachments}`.
3. `resolve_contact(sender_id)`:
   - Exact match по `contacts.telegram_id`.
   - Если множественные совпадения (не должно быть из-за UNIQUE) — лог + DLQ.
4. Определяем `display_name`: Telegram `from.username` или `first_name last_name`.
5. Создаём `Message`:
   - `source='telegram'`, `contact_id` найденного контакта или NULL.
   - Вложение: сохраняем файл в `attachments/{sender_id}/{external_id}`. Путь пишем в `attachment_path`.
6. Если контакт найден → пуш уведомление (websocket future). Если нет → попадает в `unsorted`.

### 2.3 Pipeline Email
1. Poll IMAP INBOX (фильтр `UNSEEN`).
2. Для каждого письма:
   - `sender_id = parsed_email_address`.
   - `preview = first 120 chars without HTML`.
   - Attachments пишем на диск и сохраняем относительный путь.
3. Contact resolution: match по LOWER(email). При конфликте (несколько контактов) — приоритет VIP организации, иначе первый созданный → лог + manual review.
4. Создаём сообщение аналогично Telegram.
5. После успешной вставки помечаем письмо как `Seen` (idempotency через `Message-ID`).

### 2.4 Выходящие сообщения
- `POST /api/send` добавляет запись в `messages` и ставит задачу в очередь `outbox` (redis/list).
- Worker `transport` забирает задачи и отправляет через соответствующий транспорт (Telegram Bot API или SMTP).
- Ретраи аналогичны входящим. Неудача → `is_outbound=True`, `delivery_status='failed'` (будущий столбец). UI должен показывать error badge.

### 2.5 Мониторинг
- Prometheus метрики: `anaconda_worker_processed_total{source=...}`, `anaconda_worker_failures_total`.
- Health-check endpoints `/health/telegram_worker`, `/health/email_worker`.

---

## 3. API КОНТРАКТЫ

### 3.1 Общие правила
- Формат времени: ISO8601 (UTC) `YYYY-MM-DDTHH:mm:ssZ`.
- Все ответы содержат `request_id` в header для трассировки.
- Ошибки → JSON `{ "error": { "code": "CONTACT_NOT_FOUND", "message": "..." } }`.
- Пагинация: `limit` (по умолчанию 50, макс 200), `before`/`after` `created_at` cursors.
- `unread_count` = количество записей `messages` where `contact_id=:id AND is_read=false`.

### 3.2 `GET /api/hub_structure`
| Поле | Тип | Обяз. | Описание |
| --- | --- | --- | --- |
| `unsorted[].sender_id` | string | ✓ | Технический идентификатор |
| `unsorted[].source` | enum | ✓ | `telegram`/`email` |
| `unsorted[].preview` | string | ✓ | 0..120 символов |
| `unsorted[].time` | string | ✓ | ISO8601 |
| `unsorted[].display_name` | string | ✓ | Имя из профиля (если есть) |
| `organizations[].id` | int | ✓ | |
| `organizations[].name` | string | ✓ | |
| `organizations[].is_vip` | bool | ✓ | влияет на сортировку (VIP вверх, затем алфавит) |
| `organizations[].contacts[].channels` | string[] | ✓ | `['telegram','email']` |
| `organizations[].contacts[].unread_count` | int | ✓ | badge |
| `organizations[].contacts[].display_name` | string | ✓ | если `name` пустой, fallback на email |

Параметры: `?search=...` (фильтр по имени/организации), `?only_vip=true`.

### 3.3 `GET /api/history/{contact_id}`
Ответ:
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
      "attachment_url": "/files/123/abc.png",
      "is_outbound": false,
      "is_read": true,
      "created_at": "2026-02-04T10:30:00Z"
    }
  ]
}
```
Параметры: `limit`, `before`, `after`, `include_attachments` (true → вложения проксируются). Логика объединения: `SELECT * FROM messages WHERE contact_id=:contact_id ORDER BY created_at ASC` (sender-based join устарел).

### 3.4 `POST /api/send`
Сценарии ошибок:
| Код | HTTP | Условие |
| --- | --- | --- |
| `CONTACT_NOT_FOUND` | 404 | Нет контакта |
| `CHANNEL_NOT_AVAILABLE` | 400 | У контакта нет выбранного канала |
| `VALIDATION_ERROR` | 422 | Пустой текст и нет файла |
| `ATTACHMENT_TOO_LARGE` | 413 | >10 МБ |

Формат: `multipart/form-data` (`json` часть + файл) или чистый JSON без файла. Требуется idempotency header `Idempotency-Key` — повтор запроса с тем же ключом не создаёт дубликаты.

### 3.5 `POST /api/link_contact`
Тело:
```json
{
  "sender_id": "tg_555",
  "source": "telegram",
  "name": "Петр Иванов",
  "position": "Директор",
  "org_id": 1,
  "email": "optional@example.com",
  "telegram_id": "tg_555",
  "channel": "telegram",
  "notes": "VIP"
}
```
Правила:
- `channel` обязательный, чтобы backend понимал, какое поле заполнять.
- Если контакт уже существует с этим каналом → 409 + подсказка в UI.
- После создания выполняем `UPDATE messages SET contact_id=:new_id WHERE sender_id=:sender_id AND contact_id IS NULL`.

### 3.6 Legacy совместимость
- `/api/chats`, `/api/organizations`, `/api/contacts` остаются read-only до v4.1. Надо описать в SPEC, что фронт не должен их вызывать после перехода.

---

## 4. FRONTEND / UX СПЕЦИФИКАЦИЯ

### 4.1 Компонент "Inbox"
| Состояние | Описание |
| --- | --- |
| Loading | Skeleton карточек |
| Empty | Текст "Неразобранных нет" |
| Error | Красный баннер, retry |
| Item hover | Показывает кнопку "Обработать" |

### 4.2 Компонент "Accordion"
- Группы отсортированы: VIP → остальные (A-Z).
- Организация без контактов: отображать текст "Нет привязанных сотрудников".
- Горячие клавиши: `↑/↓` — перемещение по списку, `Enter` — открыть контакт.
- Accessibility: role="tree", focus ring.

### 4.3 История сообщений
- Loading state: shimmer bubbles.
- Empty state: "Переписка пока не началась" + кнопка отправить.
- Сообщение с вложением: превью (image/pdf icon) + кнопка скачать.
- Статусы: `is_read=false` → badge "Непрочитано"; `delivery_status=failed` (будущее поле) → значок ⚠️.
- Таймстемпы локализуются на клиенте (moment/dayjs) в часовом поясе оператора.

### 4.4 Composer
- Поля: textarea (min 1 line, max 5), селектор канала (radio buttons), загрузка файла (accept images/pdf, max 10 МБ).
- Валидации: нельзя отправить пустой текст + без файла, отображать тултип.
- Горячие клавиши: `Ctrl+Enter` — отправить, `Esc` — очистить.

### 4.5 Модалка "Обработка Лида"
- Шаги:
  1. Отображаем источник (`telegram_id`/`email`).
  2. Поля: `name` (обяз.), `position` (опц.), `org_id` (select) или `new_org_name`.
  3. Checkbox "Сделать VIP" — переключает `organizations.is_vip`.
- Ошибки показываются инлайн (подсветка).
- После успешного сохранения модалка закрывается и UI обновляет дерево без перезагрузки.

### 4.6 Состояния ошибок и пустые списки
- Общие сетевые ошибки отображаются баннером в верхней части приложения.
- Если нет доступных каналов у контакта → disable composer, показать подсказку "Добавьте канал через редактирование".

---

## 5. ПЛАН ВНЕДРЕНИЯ / ROADMAP (48 ЧАСОВ)

### День 1 — Данные и Backend
1. Применить миграции (`messages`, `contacts`, индексы).
2. Обновить ORM модели (см. IMPLEMENTATION-004) и убедиться, что alembic revision покрывает новые поля.
3. Реализовать `/api/hub_structure`, `/api/history/{contact_id}`, `/api/link_contact` c учётом пагинации и `unread_count`.
4. Написать unit-тесты (pytest) для резолва контактов и формирования дерева.

### День 1 вечер — Workers/Transport
1. Настроить polling интервалы и ретраи.
2. Создать очередь `outbox` (Redis) и worker отправки.
3. Проверить переменные окружения (`TELEGRAM_BOT_TOKEN`, `EMAIL_SMTP_HOST`, `EMAIL_SMTP_PORT`, `EMAIL_SMTP_USER`, `EMAIL_SMTP_PASSWORD`, `EMAIL_IMAP_*`).

### День 2 — Frontend & QA
1. Реализовать состояния компонентов (Inbox, Accordion, History, Composer, Lead Modal).
2. Интегрировать новые поля API (display_name, is_vip, attachment_url).
3. Написать Cypress/e2e сценарии: inbox → link contact → send message → receive reply.
4. QA checklist: миграции, отправка, повторные сообщения, файлы, VIP сортировка.

### DevOps
- Обновить `docker-compose.yml`: добавить переменные, volume для `attachments/`.
- Health-check команды: `curl /healthz`, `curl /health/telegram_worker`.
- Мониторинг: подключить Prometheus endpoint `/metrics`.

---

## 6. НЕФУНКЦИОНАЛЬНЫЕ ТРЕБОВАНИЯ

| Область | Требование |
| --- | --- |
| Безопасность | JWT-аутентификация операторов, RBAC (VIP доступ только для роли `vip_operator`). Все действия логируются в аудит-таблицу `audit_log` (оператор, действие, timestamp). |
| Производительность | 50 сообщений/сек aggregate, worker latency ≤ 2s. `/api/hub_structure` должен отвечать < 500 мс при 10k контактов (использовать batch queries и кеш на 30 секунд). |
| SLA | 99.5% аптайм workers, 1 час MTTR. |
| Хранение данных | Attachments в `attachments/` (локальный диск или S3). Retention: 1 год, затем архив в холодное хранилище. |
| Логирование и трассировка | Структурные логи, request_id в headers. Поддержка OpenTelemetry (trace id проходит через workers и API). |
| Rate limiting | 60 запросов/мин на оператора для `/api/send`, 600/мин для чтения. |

---

## 7. СИНХРОНИЗАЦИЯ С РЕАЛИЗАЦИЕЙ / LEGACY

- Документ согласован с `docs/dev/IMPLEMENTATION-004.md` и `docs/dev/BUGFIX-SPEC-004.md`.
- Legacy endpoints `/api/chats`, `/api/organizations`, `/api/contacts` описаны как совместимые до версии 4.1, фронтенд обязан переключиться на `/api/hub_structure`.
- TODO из IMPLEMENTATION (загрузка файлов, редактирование контактов, поиск) перечислены в разделе 5 (roadmap) как дальнейшие итерации.
- Перечень переменных окружения фиксируется в SPEC (см. раздел 5) и должен совпадать с `env.example`.
- Любые расхождения между SPEC и кодом фиксируются в BUGFIX документах с обратной ссылкой на раздел SPEC.

---

**Критерий готовности SPEC-004**: после выполнения указанных миграций, обновления workers, API, фронтенда, UX-состояний, roadmap, NFR и legacy-совместимости команда разработки, QA и DevOps могут работать без дополнительных устных уточнений.