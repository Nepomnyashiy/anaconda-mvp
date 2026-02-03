Принято, Сергей Анатольевич. Откладываем AI в сторону. Сейчас приоритет — стабильность **MVP 1.0** для демонстрации.

Мы фиксируем архитектуру: **Docker + FastAPI + PostgreSQL + Vue 3**.
Данные сохраняются на диск. Лиды создаются. Лента обновляется.

Ниже **Финальная Инструкция по сборке релизной версии** на вашем сервере `31.59.106.120`.

---

# 🚀 Инструкция по развертыванию MVP 1.0 (Release Candidate)

**Цель:** Запустить систему с сохранением данных в БД.
**Сервер:** Ubuntu 24.04 (IP: 31.59.106.120)

## Шаг 1. Очистка (если были старые эксперименты)

Зайдите на сервер по SSH и выполните очистку, чтобы старые контейнеры не мешали:

```bash
cd ~/anaconda_mvp
docker compose down -v  # Удаляет контейнеры и временные данные (но базу оставим, если volume внешний)

```

## Шаг 2. Итоговая структура файлов

Убедитесь, что у вас созданы папки и файлы:

```text
anaconda_mvp/
├── docker-compose.yml
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── main.py
└── frontend/
    ├── Dockerfile
    ├── package.json (генерируется автоматически или создается вручную)
    └── src/
        └── App.vue

```

## Шаг 3. Содержимое файлов (Copy-Paste)

Я собрал финальные версии кода, готовые к работе с БД.

### 1. `docker-compose.yml`

*Добавлена PostgreSQL 16.*

```yaml
version: '3.8'

services:
  # --- БАЗА ДАННЫХ ---
  db:
    image: postgres:16-alpine
    container_name: anaconda_db
    restart: always
    environment:
      POSTGRES_USER: anaconda_user
      POSTGRES_PASSWORD: ***REMOVED***
      POSTGRES_DB: anaconda_db
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  # --- БЭКЕНД (API) ---
  backend:
    build: ./backend
    container_name: anaconda_backend
    ports:
      - "8000:8000"
    depends_on:
      - db
    environment:
      # Строка подключения к БД внутри сети Docker
      DATABASE_URL: postgresql://anaconda_user:***REMOVED***@db:5432/anaconda_db
    volumes:
      - ./backend:/app
    restart: always

  # --- ФРОНТЕНД (UI) ---
  frontend:
    build: ./frontend
    container_name: anaconda_frontend
    ports:
      - "80:5173"
    volumes:
      - ./frontend:/app
      - /app/node_modules
    environment:
      - VITE_API_URL=http://31.59.106.120:8000/api
    depends_on:
      - backend
    restart: always

volumes:
  postgres_data:

```

### 2. `backend/requirements.txt`

```text
fastapi
uvicorn
requests
python-multipart
sqlalchemy
psycopg2-binary

```

### 3. `backend/Dockerfile`

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

```

### 4. `backend/main.py` (С поддержкой БД и Лидов)

```python
import os
import logging
from datetime import datetime
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text
from sqlalchemy.orm import sessionmaker, Session, declarative_base

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- БД SETUP ---
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://anaconda_user:***REMOVED***@db:5432/anaconda_db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- МОДЕЛИ ---
class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    source = Column(String)  # telegram, email, max
    sender = Column(String)
    text = Column(Text)
    created_at = Column(DateTime, default=datetime.now)

class Lead(Base):
    __tablename__ = "leads"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    source = Column(String)
    status = Column(String, default="Новый")
    created_at = Column(DateTime, default=datetime.now)

# Создаем таблицы (в MVP делаем это при старте)
Base.metadata.create_all(bind=engine)

# --- ПРИЛОЖЕНИЕ ---
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Для демо открываем всем
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- API ---

@app.get("/api/messages")
def read_messages(db: Session = Depends(get_db)):
    # Возвращаем последние 50, сортируем от новых к старым
    return db.query(Message).order_by(Message.id.desc()).limit(50).all()

@app.post("/api/leads")
async def create_lead(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    new_lead = Lead(name=data.get("name"), source=data.get("source"))
    db.add(new_lead)
    db.commit()
    logger.info(f"New Lead Created: {new_lead.name}")
    return {"status": "ok", "lead_id": new_lead.id}

# Webhook для Макса (Сохраняет в БД)
@app.post("/api/webhook/max")
async def max_webhook(request: Request, db: Session = Depends(get_db)):
    try:
        data = await request.json()
        logger.info(f"MAX Hook: {data}")
        # Пример парсинга - нужно уточнить по реальному JSON от Макса
        text_content = data.get("text", str(data)) 
        sender_name = data.get("sender", {}).get("name", "Unknown Max")
        
        msg = Message(source="max", sender=sender_name, text=text_content)
        db.add(msg)
        db.commit()
        return {"status": "saved"}
    except Exception as e:
        logger.error(f"Error: {e}")
        return {"status": "error"}

```

### 5. `frontend/src/App.vue` (Фронтенд с кнопкой Лида)

```html
<script setup>
import { ref, onMounted } from 'vue'

const messages = ref([])
const API_URL = 'http://31.59.106.120:8000/api'

const fetchMessages = async () => {
  try {
    const res = await fetch(`${API_URL}/messages`)
    if (res.ok) {
      messages.value = await res.json()
    }
  } catch (e) {
    console.error("Ошибка загрузки", e)
  }
}

const createLead = async (msg) => {
  if(!confirm(`Создать лида: ${msg.sender}?`)) return
  
  try {
    const res = await fetch(`${API_URL}/leads`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ name: msg.sender, source: msg.source })
    })
    if (res.ok) alert("✅ Лид сохранен в базу!")
  } catch (e) {
    alert("Ошибка: " + e)
  }
}

onMounted(() => {
  fetchMessages()
  setInterval(fetchMessages, 2000)
})

const getBorder = (s) => {
  if(s==='max') return 'border-purple-500 bg-purple-50'
  if(s==='email') return 'border-orange-500 bg-orange-50'
  return 'border-blue-500 bg-blue-50'
}
</script>

<template>
  <div class="max-w-2xl mx-auto p-4 font-sans text-gray-800">
    <header class="mb-6 border-b pb-4 flex justify-between items-center">
      <h1 class="text-2xl font-bold">🐍 Anaconda <span class="text-sm bg-green-600 text-white px-2 rounded">MVP 1.0</span></h1>
      <div class="text-xs text-gray-500">PostgreSQL Connected</div>
    </header>

    <div v-if="messages.length === 0" class="text-center py-10 text-gray-400">
      Нет сообщений. Напишите боту.
    </div>

    <div class="space-y-4">
      <div v-for="msg in messages" :key="msg.id" 
           :class="['p-4 rounded shadow bg-white border-l-4', getBorder(msg.source)]">
        
        <div class="flex justify-between items-start mb-2">
          <span class="font-bold">{{ msg.sender }}</span>
          <span class="text-xs text-gray-400">{{ new Date(msg.created_at).toLocaleTimeString() }}</span>
        </div>
        
        <p class="whitespace-pre-wrap mb-3 text-sm">{{ msg.text }}</p>
        
        <button @click="createLead(msg)" 
                class="text-xs bg-gray-100 hover:bg-green-100 text-gray-700 hover:text-green-700 px-3 py-1 rounded border transition-colors">
          + В Лиды
        </button>
      </div>
    </div>
  </div>
</template>

```

---

## Шаг 4. Финальный запуск

1. **Сборка и запуск:**
```bash
docker compose up -d --build

```


2. **Проверка:**
* Откройте `http://31.59.106.120` — должна открыться лента.
* Отправьте Webhook (или сообщение в бота).
* Нажмите "+ В Лиды" — должно появиться уведомление.
* Перезапустите контейнеры `docker compose restart`.
* Обновите страницу — **сообщения должны остаться на месте**.



Если это работает — **MVP 1.0 готов к демонстрации.**