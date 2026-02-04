Сергей Анатольевич, это логичный и самый сложный этап — превращение «Витрины» 

# ТЕХНИЧЕСКАЯ СПЕЦИФИКАЦИЯ v3.0

**Модуль:** Полноценный обмен сообщениями (Full Duplex Messaging)
**Цель:** Реализовать отправку сообщений (Текст + Файлы), статусы прочтения и хранение полной истории в БД.

---

## 1. АРХИТЕКТУРА ДАННЫХ (Database First)

Принцип: При открытии чата мы **никогда** не запрашиваем историю у Telegram/Email API. Мы читаем только локальную таблицу `messages`.

### 1.1. Модернизация Модели `Message`

Необходимо добавить флаги направления и статуса.

**Изменения в `models.py`:**

```python
class Message(Base):
    __tablename__ = "messages"
    # ... существующие поля ...
    
    # Новые поля
    is_outbound = Column(Boolean, default=False) # True = Мы ответили, False = Клиент написал
    is_read = Column(Boolean, default=False)     # True = Менеджер открыл сообщение
    
    # Для файлов (MVP: храним путь или URL)
    attachment_path = Column(String, nullable=True) 
    attachment_name = Column(String, nullable=True)

```

---

## 2. БЭКЕНД (API & Logic)

### 2.1. Отправка сообщений (`POST /api/send`)

Единая точка входа. Бэкенд сам решает, какой транспорт использовать (SMTP или Telegram API) в зависимости от источника чата.

**Логика:**

1. Принять `chat_id`, `text`, `files`.
2. **Сразу сохранить** сообщение в БД с `is_outbound=True` (чтобы оно мгновенно появилось в UI).
3. Асинхронно отправить во внешний мир:
* **Telegram:** `requests.post(f".../sendMessage", json={"chat_id": sender_id, "text": text})`.
* **Email:** Использовать `smtplib` для отправки ответа на email.


4. Если отправка упала — пометить сообщение в БД как «Ошибка» (опционально для v3.1).

**Спецификация запроса:**

* `Multipart/form-data` (чтобы поддерживать файлы).
* Поля: `sender_id` (куда шлем), `source` (канал), `text` (сообщение), `file` (бинарник).

### 2.2. Статус прочтения (`POST /api/chats/{chat_id}/read`)

Вызывается фронтендом, когда пользователь открывает чат.

**Логика:**

```sql
UPDATE messages 
SET is_read = TRUE 
WHERE sender_id = :chat_id AND is_outbound = FALSE;

```

* Это должно сбросить счетчик `unread` в левом меню.

### 2.3. Получение истории (`GET /api/messages?sender_id=...`)

Фильтрация по конкретному чату.

---

## 3. ФРОНТЕНД (UI/UX)

### 3.1. Окно чата (Лента сообщений)

Необходимо визуально разделить «Наши» и «Чужие» сообщения.

* **Входящее (Клиент):**
* Выравнивание: **Слева**.
* Фон: Белый (`bg-white`).
* Бордер: Цвет источника (Синий для TG, Красный для Email).


* **Исходящее (Мы):**
* Выравнивание: **Справа**.
* Фон: Светло-зеленый (`bg-green-50`) или фирменный светлый (`bg-slate-100`).
* Статус: Галочка (отправлено).



### 3.2. Панель ввода (Input Area)

* **Текстовое поле:** `textarea` с авто-высотой (1-5 строк).
* **Скрепка:** Стандартный `<input type="file" hidden>`, вызываемый по клику на иконку. При выборе файла показывать его имя над строкой ввода.
* **Кнопка отправки:** Блокируется, если поле пустое. При нажатии — анимация загрузки.

### 3.3. Header Чата (Кнопки действий)

Добавить панель быстрых действий CRM прямо в шапку.

* Кнопка **[+ Контакт]** (если `is_known = false`).
* Кнопка **[+ Организация]** (привязать к юрлицу).
* Кнопка **[Сделка]** (Create Deal - заготовка на будущее).

---

## 4. РЕАЛИЗАЦИЯ (Код для разработчика)

### 4.1. Обновленный Backend (`main.py`)

Добавляем эндпоинты отправки и прочтения.

```python
# ... (imports: shutil, UploadFile, File)

@app.post("/api/send")
async def send_message(
    source: str = Form(...),
    sender_id: str = Form(...),
    text: str = Form(...),
    file: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    # 1. Логика сохранения файла (локально)
    file_path = None
    if file:
        file_path = f"uploads/{file.filename}"
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

    # 2. Сохраняем в БД (Сразу, чтобы интерфейс обновился)
    db_msg = Message(
        source=source,
        sender_id=sender_id,
        sender="Менеджер", # Или из токена авторизации
        text=text,
        is_outbound=True,  # ВАЖНО: Это исходящее
        is_read=True,
        attachment_path=file_path
    )
    db.add(db_msg)
    db.commit()

    # 3. Отправка во внешний мир
    if source == "telegram":
        # Отправка в Telegram
        tg_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(tg_url, json={"chat_id": sender_id, "text": text})
        
        if file:
            # Отдельная логика для sendDocument...
            pass

    return {"status": "sent", "msg_id": db_msg.id}

@app.post("/api/read/{sender_id}")
def mark_as_read(sender_id: str, db: Session = Depends(get_db)):
    """Пометить все сообщения в чате как прочитанные"""
    db.query(Message).filter(
        Message.sender_id == sender_id,
        Message.is_outbound == False,
        Message.is_read == False
    ).update({"is_read": True})
    db.commit()
    return {"status": "ok"}

```

### 4.2. Обновленный Frontend (`App.vue`)

Изменения в секции чата.

```html
<div class="h-16 bg-white border-b flex justify-between items-center px-4">
  <div class="font-bold">{{ selectedChat.display_name }}</div>
  
  <div class="flex gap-2">
     <button v-if="!selectedChat.org_name" @click="openLinkOrgModal" 
             class="text-xs bg-slate-100 hover:bg-slate-200 px-3 py-1 rounded border">
        <i class="fa-solid fa-building"></i> + Орг
     </button>
     <button v-if="!isContactKnown" @click="openCreateContactModal"
             class="text-xs bg-red-50 text-red-600 hover:bg-red-100 px-3 py-1 rounded border border-red-200">
        <i class="fa-solid fa-user-plus"></i> + Контакт
     </button>
  </div>
</div>

<div class="flex-1 overflow-y-auto p-4 bg-[#e5ddd5]/30 flex flex-col gap-3">
   <div v-for="msg in selectedChatMessages" :key="msg.id"
        class="max-w-[70%] p-3 rounded-lg text-sm shadow-sm relative"
        :class="msg.is_outbound 
           ? 'self-end bg-green-50 border border-green-100 rounded-tr-none' 
           : 'self-start bg-white border border-slate-200 rounded-tl-none'">
        
        <div class="whitespace-pre-wrap">{{ msg.text }}</div>
        
        <div v-if="msg.attachment_path" class="mt-2 flex items-center gap-2 bg-black/5 p-2 rounded">
           <i class="fa-solid fa-file"></i> 
           <span class="text-xs underline">Файл</span>
        </div>

        <div class="text-[10px] text-right mt-1 opacity-50 flex justify-end gap-1">
           {{ formatTime(msg.created_at) }}
           <i v-if="msg.is_outbound" class="fa-solid fa-check"></i>
        </div>
   </div>
</div>

<div class="bg-white p-2 border-t flex items-center gap-2">
   <input type="file" ref="fileInput" class="hidden" @change="handleFileSelect">
   <button @click="$refs.fileInput.click()" class="p-3 text-slate-400 hover:text-slate-600">
      <i class="fa-solid fa-paperclip"></i>
   </button>

   <textarea v-model="newMessageText" @keydown.enter.exact.prevent="sendMessage"
             class="flex-1 bg-slate-100 rounded-lg py-2 px-4 focus:outline-none resize-none h-10 leading-6"
             placeholder="Написать сообщение..."></textarea>
   
   <button @click="sendMessage" class="p-3 text-blue-600 hover:bg-blue-50 rounded-full transition">
      <i class="fa-solid fa-paper-plane text-xl"></i>
   </button>
</div>

```

---

## 5. СЦЕНАРИИ ТЕСТИРОВАНИЯ (QA)

1. **Отправка в Telegram:**
* Открыть чат с Telegram-юзером.
* Написать "Привет". Нажать Enter.
* **Ожидание:** Сообщение мгновенно появилось справа на зеленом фоне. Через 1-2 сек оно пришло в реальный Telegram клиенту.


2. **Получение ответа:**
* Ответить с телефона в Telegram.
* **Ожидание:** Через 5 секунд (цикл опроса) сообщение появилось в ленте слева на белом фоне.


3. **Прочтение:**
* Пришло новое сообщение (счетчик горит красным).
* Кликнули на чат.
* **Ожидание:** Счетчик исчез или уменьшился. В базе `is_read` стало `True`.


4. **Файл:**
* Нажать скрепку, выбрать PDF. Написать текст. Отправить.
* **Ожидание:** В ленте появился блок с иконкой файла. Клиент получил документ.



Эта спецификация делает систему замкнутой и самодостаточной. Можно приступать к реализации.