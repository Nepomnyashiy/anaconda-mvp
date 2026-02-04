import os
import logging
import asyncio
import threading
import imaplib
import email
from email.header import decode_header
from datetime import datetime
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, ForeignKey, Boolean, or_, and_
from sqlalchemy.orm import sessionmaker, Session, declarative_base, relationship
from pydantic import BaseModel
from typing import Optional
import requests

# --- ЛОГИРОВАНИЕ ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- КОНФИГУРАЦИЯ ---
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://anaconda_user:***REMOVED***@db:5432/anaconda_db")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_BOT_USERNAME = os.getenv("TELEGRAM_BOT_USERNAME", "anaconda_mvp_bot")
TELEGRAM_WEBHOOK_URL = os.getenv("TELEGRAM_WEBHOOK_URL", "http://localhost:8000/api/webhook/telegram")
TELEGRAM_USE_POLLING = os.getenv("TELEGRAM_USE_POLLING", "false").lower() == "true"

# Email IMAP
EMAIL_IMAP_HOST = os.getenv("EMAIL_IMAP_HOST", "imap.yandex.ru")
EMAIL_IMAP_PORT = int(os.getenv("EMAIL_IMAP_PORT", "993"))
EMAIL_IMAP_USER = os.getenv("EMAIL_IMAP_USER", "")
EMAIL_IMAP_PASSWORD = os.getenv("EMAIL_IMAP_PASSWORD", "")
EMAIL_IMAP_SSL = os.getenv("EMAIL_IMAP_SSL", "true").lower() == "true"

logger.info(f"TELEGRAM_BOT_TOKEN: {TELEGRAM_BOT_TOKEN[:20]}..." if TELEGRAM_BOT_TOKEN else "TELEGRAM_BOT_TOKEN not set")
logger.info(f"TELEGRAM_WEBHOOK_URL: {TELEGRAM_WEBHOOK_URL}")
logger.info(f"EMAIL_IMAP_HOST: {EMAIL_IMAP_HOST}, PORT: {EMAIL_IMAP_PORT}")
logger.info(f"EMAIL_IMAP_USER: {EMAIL_IMAP_USER if EMAIL_IMAP_USER else 'not set'}")

# --- БД SETUP ---
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- МОДЕЛИ ---
class Organization(Base):
    __tablename__ = "organizations"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)  # "ПАО Газпром"
    inn = Column(String, nullable=True, index=True)  # Для проверки дублей
    is_vip = Column(Boolean, default=False)  # Метка VIP (Корона)
    
    # Связь: Одна компания -> Много сотрудников
    contacts = relationship("Contact", back_populates="org")

class Contact(Base):
    __tablename__ = "contacts"
    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    
    # Персональные данные
    name = Column(String, index=True)  # "Иванов Иван"
    position = Column(String, nullable=True)  # "Главный инженер"
    
    # Ключи связи (Identity Keys)
    email = Column(String, index=True, unique=True, nullable=True)
    telegram_id = Column(String, index=True, unique=True, nullable=True)
    
    created_at = Column(DateTime, default=datetime.now)
    
    # Relationship
    org = relationship("Organization", back_populates="contacts")
    messages = relationship("Message", back_populates="contact")

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    source = Column(String)  # telegram, email, max
    sender = Column(String)
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=True, index=True)
    sender_id = Column(String, index=True, nullable=True)
    text = Column(Text)
    is_outbound = Column(Boolean, default=False)  # True = мы отправили
    is_read = Column(Boolean, default=False)  # Статус прочтения
    attachment_path = Column(String, nullable=True)  # Путь к файлу вложения
    created_at = Column(DateTime, default=datetime.now)
    
    contact = relationship("Contact", back_populates="messages")

class Lead(Base):
    __tablename__ = "leads"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    source = Column(String)
    status = Column(String, default="Новый")
    created_at = Column(DateTime, default=datetime.now)

# Создаем таблицы при старте
Base.metadata.create_all(bind=engine)

# --- PYDANTIC МОДЕЛИ ---
class ContactCreate(BaseModel):
    """
    Создание контакта с поддержкой выбора или создания Organization.
    
    Примеры:
    1. Привязать к существующей организации:
       {"name": "Иван", "position": "Инженер", "sender_id": "tg_123", 
        "source": "telegram", "org_id": 5}
    
    2. Создать новую организацию:
       {"name": "Иван", "position": "Инженер", "sender_id": "tg_123",
        "source": "telegram", "org_mode": "new", "new_org_name": "ООО Газпром"}
    """
    sender_id: str  # Кого привязываем (email или telegram_id)
    name: str
    position: str = None
    source: str = None  # "email" или "telegram"
    
    # Режимы связи с Organization
    org_mode: str = None  # "existing" | "new" | None (не привязывать)
    org_id: int = None  # Если org_mode="existing"
    new_org_name: str = None  # Если org_mode="new"
    inn: str = None  # Для новой организации

class OrganizationCreate(BaseModel):
    name: str
    inn: str = None
    is_vip: bool = False

class SendMessageRequest(BaseModel):
    """Запрос на отправку сообщения (SPEC-004)"""
    contact_id: int = None  # ID контакта из БД (опционально)
    sender_id: str = None   # Для неразобранных контактов (опционально)
    channel: str  # "telegram" или "email"
    text: str
    # file: str = None  # base64 или путь (TODO: реализовать)

class ContactUpdate(BaseModel):
    name: Optional[str] = None
    position: Optional[str] = None
    org_id: Optional[int] = None
    email: Optional[str] = None
    telegram_id: Optional[str] = None


# --- ПРИЛОЖЕНИЕ ---
app = FastAPI(title="Anaconda MVP 1.0", description="Корпоративная платформа для единого окна продаж")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- ЗАВИСИМОСТЬ ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- TELEGRAM POLLING ---
last_update_id = 0
telegram_polling_active = False

def telegram_polling_worker():
    """Background worker для получения сообщений из Telegram методом polling"""
    global last_update_id, telegram_polling_active
    
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("⚠ Telegram polling disabled: TELEGRAM_BOT_TOKEN not configured")
        return
    
    telegram_polling_active = True
    logger.info("✓ Telegram polling started")
    
    while telegram_polling_active:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
            params = {
                "offset": last_update_id,
                "allowed_updates": ["message"],
                "timeout": 30
            }
            
            response = requests.get(url, params=params, timeout=35)
            data = response.json()
            
            if data.get("ok"):
                updates = data.get("result", [])
                
                for update in updates:
                    update_id = update.get("update_id")
                    last_update_id = update_id + 1
                    
                    if "message" in update:
                        message_data = update["message"]
                        from_user = message_data.get("from", {})
                        
                        sender_name = f"{from_user.get('first_name', '')} {from_user.get('last_name', '')}".strip()
                        if not sender_name:
                            sender_name = from_user.get("username", "Unknown")
                        
                        # sender_id для Telegram - это user_id
                        sender_id = str(from_user.get("id", "unknown"))
                        text_content = message_data.get("text", "")
                        
                        if text_content:
                            db = SessionLocal()
                            try:
                                msg = Message(source="telegram", sender=sender_name, sender_id=sender_id, text=text_content)
                                db.add(msg)
                                db.commit()
                                logger.info(f"✓ Telegram message saved: {sender_name} - {text_content[:50]}")
                            except Exception as e:
                                logger.error(f"Error saving message: {e}")
                                db.rollback()
                            finally:
                                db.close()
            else:
                logger.error(f"Telegram API error: {data.get('description', 'Unknown')}")
        
        except requests.exceptions.Timeout:
            logger.debug("Telegram polling timeout (expected)")
        except Exception as e:
            logger.error(f"Telegram polling error: {e}")
            import time
            time.sleep(5)

# --- EMAIL IMAP POLLING ---
last_email_uid = {}
email_polling_active = False

def decode_email_header(header_str):
    """Декодирует email header (работает с encoded-word format)"""
    if not header_str:
        return ""
    try:
        decoded = decode_header(header_str)
        result = ""
        for part, encoding in decoded:
            if isinstance(part, bytes):
                result += part.decode(encoding or "utf-8", errors="ignore")
            else:
                result += str(part)
        return result
    except:
        return str(header_str)

def email_polling_worker():
    """Background worker для получения писем из IMAP"""
    global email_polling_active
    
    if not EMAIL_IMAP_USER or not EMAIL_IMAP_PASSWORD:
        logger.warning("⚠ Email polling disabled: EMAIL_IMAP credentials not configured")
        return
    
    email_polling_active = True
    logger.info("✓ Email IMAP polling started")
    
    while email_polling_active:
        try:
            # Подключаемся к IMAP серверу
            if EMAIL_IMAP_SSL:
                mail = imaplib.IMAP4_SSL(EMAIL_IMAP_HOST, EMAIL_IMAP_PORT)
            else:
                mail = imaplib.IMAP4(EMAIL_IMAP_HOST, EMAIL_IMAP_PORT)
            
            mail.login(EMAIL_IMAP_USER, EMAIL_IMAP_PASSWORD)
            logger.debug("✓ IMAP connected and logged in")
            
            # Выбираем папку INBOX
            mail.select("INBOX")
            
            # Получаем последние письма (максимум 10)
            status, messages = mail.search(None, "ALL")
            if status == "OK":
                email_ids = messages[0].split()[-10:]  # Последние 10 писем
                
                for email_id in email_ids:
                    # Проверяем, не обработали ли мы это письмо
                    if "INBOX" not in last_email_uid:
                        last_email_uid["INBOX"] = set()
                    
                    email_id_str = email_id.decode() if isinstance(email_id, bytes) else email_id
                    
                    if email_id_str in last_email_uid["INBOX"]:
                        continue
                    
                    last_email_uid["INBOX"].add(email_id_str)
                    
                    # Получаем содержимое письма
                    status, email_data = mail.fetch(email_id, "(RFC822)")
                    if status == "OK":
                        try:
                            email_body = email_data[0][1]
                            email_message = email.message_from_bytes(email_body)
                            
                            # Получаем отправителя с декодированием
                            from_header = email_message.get("From", "Unknown")
                            sender = decode_email_header(from_header)
                            
                            # Парсим email адрес из "Name <email@domain>" и используем как sender_id
                            if "<" in sender and ">" in sender:
                                sender_id = sender.split("<")[1].split(">")[0]
                                sender_name = sender.split("<")[0].strip()
                            else:
                                sender_id = sender
                                sender_name = sender.split("@")[0] if "@" in sender else sender
                            
                            # Получаем тему с декодированием
                            subject_header = email_message.get("Subject", "(no subject)")
                            subject = decode_email_header(subject_header)
                            
                            # Получаем текст письма
                            text_content = ""
                            if email_message.is_multipart():
                                for part in email_message.walk():
                                    if part.get_content_type() == "text/plain":
                                        payload = part.get_payload(decode=True)
                                        if payload:
                                            text_content = payload.decode("utf-8", errors="ignore")
                                        break
                            else:
                                payload = email_message.get_payload(decode=True)
                                if payload:
                                    text_content = payload.decode("utf-8", errors="ignore")
                            
                            # Комбинируем тему и текст
                            full_text = f"[{subject}]\n{text_content[:500]}" if text_content else f"[{subject}]"
                            
                            # Сохраняем в БД
                            db = SessionLocal()
                            try:
                                msg = Message(source="email", sender=sender_name, sender_id=sender_id, text=full_text)
                                db.add(msg)
                                db.commit()
                                logger.info(f"✓ Email saved: {sender_name} ({sender_id}) - {subject[:50]}")
                            except Exception as e:
                                logger.error(f"Error saving email: {e}")
                                db.rollback()
                            finally:
                                db.close()
                        except Exception as e:
                            logger.error(f"Error parsing email: {e}")
            
            mail.close()
            mail.logout()
            
            # Ждем 60 секунд перед следующей проверкой
            import time
            time.sleep(60)
        
        except imaplib.IMAP4.error as e:
            logger.error(f"IMAP error: {e}")
            import time
            time.sleep(30)
        except Exception as e:
            logger.error(f"Email polling error: {e}")
            import time
            time.sleep(30)

# --- API ENDPOINTS ---

@app.get("/")
def root():
    return {"status": "ok", "service": "Anaconda MVP 1.0"}

@app.get("/health")
def health_check():
    try:
        with engine.connect() as conn:
            from sqlalchemy import text
            conn.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "database": "connected",
            "telegram_polling": telegram_polling_active,
            "email_polling": email_polling_active
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"status": "unhealthy", "database": "disconnected"}

@app.get("/api/messages")
def read_messages(db: Session = Depends(get_db)):
    """Получить последние 50 сообщений"""
    return db.query(Message).order_by(Message.id.desc()).limit(50).all()

@app.post("/api/leads")
async def create_lead(request: Request, db: Session = Depends(get_db)):
    """Создать новый лид"""
    data = await request.json()
    new_lead = Lead(name=data.get("name"), source=data.get("source"))
    db.add(new_lead)
    db.commit()
    logger.info(f"New Lead Created: {new_lead.name}")
    return {"status": "ok", "lead_id": new_lead.id}

@app.post("/api/webhook/telegram")
async def telegram_webhook(request: Request, db: Session = Depends(get_db)):
    """Webhook для Telegram (для совместимости)"""
    try:
        data = await request.json()
        logger.info(f"Telegram webhook received: {data}")
        
        if "message" in data:
            message_data = data["message"]
            from_user = message_data.get("from", {})
            
            sender_name = f"{from_user.get('first_name', '')} {from_user.get('last_name', '')}".strip()
            if not sender_name:
                sender_name = from_user.get("username", "Unknown")
            
            text_content = message_data.get("text", "")
            
            msg = Message(source="telegram", sender=sender_name, text=text_content)
            db.add(msg)
            db.commit()
            logger.info(f"✓ Telegram message saved: {sender_name}")
            return {"status": "ok"}
        
        return {"status": "ignored"}
    except Exception as e:
        logger.error(f"Telegram webhook error: {e}")
        return {"status": "error", "error": str(e)}

@app.post("/api/webhook/max")
async def max_webhook(request: Request, db: Session = Depends(get_db)):
    """Webhook для Max (CRM)"""
    try:
        data = await request.json()
        logger.info(f"MAX Hook: {data}")
        
        text_content = data.get("text", str(data))
        sender_name = data.get("sender", {}).get("name", "Unknown Max")
        
        msg = Message(source="max", sender=sender_name, text=text_content)
        db.add(msg)
        db.commit()
        return {"status": "saved"}
    except Exception as e:
        logger.error(f"Error: {e}")
        return {"status": "error"}

@app.get("/api/telegram/setup")
async def setup_telegram_webhook():
    """Настроить webhook для Telegram"""
    if not TELEGRAM_BOT_TOKEN:
        return {"status": "error", "message": "TELEGRAM_BOT_TOKEN not configured"}
    
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook"
        payload = {
            "url": TELEGRAM_WEBHOOK_URL,
            "allowed_updates": ["message"]
        }
        response = requests.post(url, json=payload)
        result = response.json()
        
        if result.get("ok"):
            logger.info(f"✓ Telegram webhook configured: {TELEGRAM_WEBHOOK_URL}")
            return {
                "status": "ok", 
                "message": f"Webhook set to {TELEGRAM_WEBHOOK_URL}",
                "result": result
            }
        else:
            logger.error(f"Telegram API error: {result}")
            return {
                "status": "error",
                "message": result.get("description", "Unknown error")
            }
    except Exception as e:
        logger.error(f"Error setting webhook: {e}")
        return {"status": "error", "error": str(e)}

@app.get("/api/telegram/info")
async def telegram_info():
    """Информация о боте и webhook'е"""
    if not TELEGRAM_BOT_TOKEN:
        return {"status": "error", "message": "TELEGRAM_BOT_TOKEN not configured"}
    
    try:
        # Получим информацию о боте
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getMe"
        bot_info = requests.get(url).json()
        
        # Получим информацию о webhook'е
        webhook_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getWebhookInfo"
        webhook_info = requests.get(webhook_url).json()
        
        return {
            "bot": bot_info.get("result"),
            "webhook": webhook_info.get("result"),
            "webhook_url": TELEGRAM_WEBHOOK_URL,
            "polling_active": telegram_polling_active
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.get("/api/email/info")
async def email_info():
    """Информация о Email IMAP polling'е"""
    return {
        "imap_host": EMAIL_IMAP_HOST,
        "imap_port": EMAIL_IMAP_PORT,
        "imap_user": EMAIL_IMAP_USER if EMAIL_IMAP_USER else "not configured",
        "polling_active": email_polling_active,
        "last_checked_uids": len(last_email_uid.get("INBOX", []))
    }

# --- CRM ENDPOINTS ---

@app.get("/api/chats")
async def get_chats(db: Session = Depends(get_db)):
    """
    Получить иерархический список диалогов (SPEC-2.0):
    {
      "unsorted": [...],  // Неизвестные контакты
      "groups": [...]      // Компании с контактами
    }
    """
    from sqlalchemy import desc
    
    # 1. Получаем все сообщения, группируем по sender_id
    all_messages = db.query(Message).order_by(desc(Message.created_at)).all()
    
    # Словарь: sender_id -> последнее сообщение
    latest_by_sender = {}
    for msg in all_messages:
        if msg.sender_id and msg.sender_id not in latest_by_sender:
            latest_by_sender[msg.sender_id] = msg
    
    # 2. Разделяем на "известные" и "неизвестные"
    unsorted_chats = []
    org_chats = {}  # org_id -> {contacts, total_unread, last_activity_ts}
    
    for sender_id, last_msg in latest_by_sender.items():
        # Ищем контакт в БД
        contact = None
        if last_msg.source == "email":
            contact = db.query(Contact).filter(Contact.email == sender_id).first()
        elif last_msg.source == "telegram":
            contact = db.query(Contact).filter(Contact.telegram_id == sender_id).first()
        
        # Подсчитываем непрочитанные
        unread_count = db.query(Message).filter(Message.sender_id == sender_id).count()
        
        chat_item = {
            "chat_id": f"{last_msg.source}_{sender_id}",
            "source": last_msg.source,
            "sender_id": sender_id,
            "display_name": contact.name if contact else last_msg.sender,
            "preview": last_msg.text[:80] if last_msg.text else "",
            "time": last_msg.created_at.strftime("%H:%M") if last_msg.created_at else "",
            "unread": unread_count
        }
        
        # 3. Если контакт не найден -> "Неразобранное"
        if not contact or not contact.org_id:
            unsorted_chats.append(chat_item)
        else:
            # 4. Если есть org_id -> добавляем в группу
            org_id = contact.org_id
            
            if org_id not in org_chats:
                org = db.query(Organization).filter(Organization.id == org_id).first()
                org_chats[org_id] = {
                    "org_id": org_id,
                    "org_name": org.name if org else "Unknown",
                    "is_vip": org.is_vip if org else False,
                    "contacts": [],
                    "total_unread": 0,
                    "last_activity_ts": 0
                }
            
            # Добавляем позицию контакта
            chat_item["position"] = contact.position
            chat_item["display_name"] = contact.name
            
            org_chats[org_id]["contacts"].append(chat_item)
            org_chats[org_id]["total_unread"] += unread_count
            org_chats[org_id]["last_activity_ts"] = max(
                org_chats[org_id]["last_activity_ts"],
                chat_item["last_activity_ts"]
            )
    
    # 5. Сортируем группы по last_activity_ts (новые сверху)
    groups = sorted(org_chats.values(), key=lambda x: x["last_activity_ts"], reverse=True)
    
    # 6. Сортируем контакты внутри групп по последней активности
    for group in groups:
        group["contacts"] = sorted(group["contacts"], key=lambda x: x["last_activity_ts"], reverse=True)
    
    return {
        "unsorted": unsorted_chats,
        "groups": groups
    }

@app.post("/api/contacts")
async def create_contact(contact: ContactCreate, db: Session = Depends(get_db)):
    """
    Создать новый контакт и привязать его к Organization.
    Поддерживает три режима:
    1. Привязка к существующей организации (org_id)
    2. Создание новой организации (new_org_name)
    3. Без привязки (org_mode=None)
    """
    try:
        # 1. Определяем email/telegram_id из sender_id и source
        email = None
        telegram_id = None
        
        if contact.source == "email":
            email = contact.sender_id
        elif contact.source == "telegram":
            telegram_id = contact.sender_id
        
        # 2. Проверяем, не существует ли уже контакт
        if email:
            existing = db.query(Contact).filter(Contact.email == email).first()
            if existing:
                return {
                    "status": "error",
                    "message": f"Contact with email {email} already exists (id={existing.id})"
                }
        
        if telegram_id:
            existing = db.query(Contact).filter(Contact.telegram_id == telegram_id).first()
            if existing:
                return {
                    "status": "error",
                    "message": f"Contact with telegram_id {telegram_id} already exists (id={existing.id})"
                }
        
        # 3. Обработка Organization
        org_id = None
        
        if contact.org_mode == "existing":
            # Привязка к существующей организации
            if not contact.org_id:
                return {"status": "error", "message": "org_id required for org_mode='existing'"}
            
            org = db.query(Organization).filter(Organization.id == contact.org_id).first()
            if not org:
                return {"status": "error", "message": f"Organization with id={contact.org_id} not found"}
            
            org_id = contact.org_id
            logger.info(f"✓ Contact will be linked to existing org: {org.name}")
        
        elif contact.org_mode == "new":
            # Создание новой организации
            if not contact.new_org_name:
                return {"status": "error", "message": "new_org_name required for org_mode='new'"}
            
            # Проверяем, не существует ли организация с таким именем
            existing_org = db.query(Organization).filter(
                Organization.name == contact.new_org_name
            ).first()
            
            if existing_org:
                org_id = existing_org.id
                logger.info(f"✓ Organization already exists: {existing_org.name} (id={org_id})")
            else:
                # Создаем новую организацию
                new_org = Organization(
                    name=contact.new_org_name,
                    inn=contact.inn,
                    is_vip=False
                )
                db.add(new_org)
                db.commit()
                db.refresh(new_org)
                
                org_id = new_org.id
                logger.info(f"✓ New organization created: {new_org.name} (id={org_id})")
        
        # 4. Создаем контакт
        new_contact = Contact(
            name=contact.name,
            position=contact.position,
            org_id=org_id,
            email=email,
            telegram_id=telegram_id
        )
        
        db.add(new_contact)
        db.commit()
        db.refresh(new_contact)
        
        logger.info(
            f"✓ Contact created: {contact.name} (id={new_contact.id}, "
            f"email={email}, telegram_id={telegram_id}, org_id={org_id})"
        )
        
        return {
            "status": "ok",
            "contact": {
                "id": new_contact.id,
                "name": new_contact.name,
                "position": new_contact.position,
                "org_id": new_contact.org_id,
                "email": new_contact.email,
                "telegram_id": new_contact.telegram_id,
                "created_at": new_contact.created_at.isoformat()
            }
        }
    
    except Exception as e:
        logger.error(f"Error creating contact: {e}")
        db.rollback()
        return {"status": "error", "message": str(e)}


@app.patch("/api/contacts/{contact_id}")
async def update_contact(contact_id: int, payload: ContactUpdate, db: Session = Depends(get_db)):
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    if payload.name:
        contact.name = payload.name
    if payload.position:
        contact.position = payload.position
    if payload.org_id is not None:
        contact.org_id = payload.org_id
    if payload.email:
        contact.email = payload.email
    if payload.telegram_id:
        contact.telegram_id = payload.telegram_id

    db.commit()
    db.refresh(contact)

    return {
        "status": "ok",
        "contact": {
            "id": contact.id,
            "name": contact.name,
            "position": contact.position,
            "org_id": contact.org_id,
            "email": contact.email,
            "telegram_id": contact.telegram_id
        }
    }

@app.get("/api/organizations")
async def get_organizations(db: Session = Depends(get_db)):
    """Получить список организаций"""
    orgs = db.query(Organization).all()
    return [{"id": o.id, "name": o.name, "is_vip": bool(o.is_vip)} for o in orgs]

@app.post("/api/organizations")
async def create_organization(org: OrganizationCreate, db: Session = Depends(get_db)):
    """Создать организацию"""
    new_org = Organization(name=org.name, is_vip=int(org.is_vip))
    db.add(new_org)
    db.commit()
    db.refresh(new_org)
    return {"id": new_org.id, "name": new_org.name, "is_vip": bool(new_org.is_vip)}


# --- SPEC-004: НОВЫЕ API ENDPOINTS ---

@app.get("/api/hub_structure")
async def get_hub_structure(db: Session = Depends(get_db)):
    """
    SPEC-004: GET /api/hub_structure
    Возвращает полное дерево для левого меню:
    {
      "unsorted": [{"sender_id": "...", "source": "...", "preview": "...", "time": "..."}],
      "organizations": [{"id": 1, "name": "...", "contacts": [...]}]
    }
    """
    from sqlalchemy import desc

    batch_msgs = db.query(Message).filter(Message.is_outbound == False).order_by(desc(Message.created_at)).all()

    unsorted_map: dict[str, dict] = {}
    contact_map: dict[int, dict] = {}

    for msg in batch_msgs:
        key = msg.sender_id or f"{msg.source}_{msg.id}"
        if key in unsorted_map:
            continue

        preview = (msg.text or "")[:80]
        timestamp = msg.created_at.isoformat() if msg.created_at else ""

        base_entry = {
            "sender_id": msg.sender_id,
            "source": msg.source,
            "preview": preview,
            "time": timestamp,
            "display_name": msg.sender or msg.sender_id,
            "last_message": preview,
            "last_message_time": timestamp,
            "unread": db.query(Message).filter(
                Message.sender_id == msg.sender_id,
                Message.is_outbound == False,
                Message.is_read == False
            ).count()
        }

        contact = None
        if msg.source == "telegram":
            contact = db.query(Contact).filter(Contact.telegram_id == msg.sender_id).first()
        elif msg.source == "email":
            contact = db.query(Contact).filter(Contact.email == msg.sender_id).first()

        if contact and contact.org_id:
            if contact.org_id not in contact_map:
                contact_map[contact.org_id] = {
                    "org_id": contact.org_id,
                    "contacts": [],
                    "total_unread": 0,
                    "last_activity_time": None
                }

            channels = []
            if contact.telegram_id:
                channels.append("telegram")
            if contact.email:
                channels.append("email")

            contact_entry = {
                "contact_id": contact.id,
                "display_name": contact.name,
                "position": contact.position or "",
                "channels": channels,
                "source": msg.source,
                "last_message": preview,
                "last_message_time": timestamp,
                "unread": base_entry["unread"]
            }

            contact_map[contact.org_id]["contacts"].append(contact_entry)
            contact_map[contact.org_id]["total_unread"] += base_entry["unread"]

            if msg.created_at:
                current = contact_map[contact.org_id]["last_activity_time"]
                if not current or msg.created_at > current:
                    contact_map[contact.org_id]["last_activity_time"] = msg.created_at
        else:
            unsorted_map[key] = {
                **base_entry,
                "chat_id": f"{msg.source}_{key}"
            }

    organizations = []
    for org_id, bucket in contact_map.items():
        org = db.query(Organization).filter(Organization.id == org_id).first()
        if not org:
            continue

        organizations.append({
            "id": org.id,
            "name": org.name,
            "is_vip": bool(org.is_vip),
            "total_unread": bucket["total_unread"],
            "last_activity_time": bucket["last_activity_time"].isoformat() if bucket["last_activity_time"] else "",
            "contacts": bucket["contacts"]
        })

    organizations.sort(key=lambda x: (not x["is_vip"], x["name"]))

    return {
        "unsorted": list(unsorted_map.values()),
        "organizations": organizations
    }


@app.get("/api/messages/by_sender/{sender_id}")
async def get_messages_by_sender(sender_id: str, db: Session = Depends(get_db)):
    """
    Получить историю сообщений по sender_id (для неразобранных контактов).
    Возвращает сообщения + информацию об отправителе.
    """
    from sqlalchemy import asc
    from urllib.parse import unquote
    
    # Декодируем sender_id (может содержать @ для email)
    sender_id = unquote(sender_id)
    
    # Получаем все сообщения для этого sender_id
    messages = db.query(Message).filter(
        Message.sender_id == sender_id
    ).order_by(asc(Message.created_at)).all()
    
    if not messages:
        raise HTTPException(status_code=404, detail=f"No messages found for sender_id={sender_id}")
    
    # Определяем source и sender_name из первого сообщения
    first_msg = messages[0]
    
    # Отмечаем входящие как прочитанные
    db.query(Message).filter(
        Message.sender_id == sender_id,
        Message.is_read == False,
        Message.is_outbound == False
    ).update({Message.is_read: True}, synchronize_session=False)
    db.commit()
    
    return {
        "sender_info": {
            "sender_id": sender_id,
            "source": first_msg.source,
            "display_name": first_msg.sender
        },
        "messages": [
            {
                "id": m.id,
                "source": m.source,
                "text": m.text,
                "is_outbound": bool(m.is_outbound),
                "is_read": bool(m.is_read),
                "created_at": m.created_at.isoformat() if m.created_at else None
            } for m in messages
        ]
    }


@app.get("/api/history/{contact_id}")
async def get_contact_history(contact_id: int, db: Session = Depends(get_db)):
    """
    SPEC-004: GET /api/history/{contact_id}
    Агрегирует историю из всех каналов этого человека.
    """
    from sqlalchemy import or_, asc
    
    # 1. Получаем контакт
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail=f"Contact {contact_id} not found")
    
    # 2. Собираем условия поиска по всем каналам контакта
    conditions = []
    if contact.email:
        conditions.append(Message.sender_id == contact.email)
    if contact.telegram_id:
        conditions.append(Message.sender_id == contact.telegram_id)
    
    if not conditions:
        return {"contact": {"id": contact.id, "name": contact.name}, "messages": []}
    
    # 3. Получаем все сообщения (входящие + исходящие)
    messages = db.query(Message).filter(or_(*conditions)).order_by(asc(Message.created_at)).all()
    
    # 4. Отмечаем как прочитанные
    db.query(Message).filter(
        or_(*conditions),
        Message.is_read == False,
        Message.is_outbound == False
    ).update({Message.is_read: True}, synchronize_session=False)
    db.commit()
    
    # 5. Формируем ответ
    result_messages = []
    for msg in messages:
        result_messages.append({
            "id": msg.id,
            "source": msg.source,
            "text": msg.text,
            "is_outbound": bool(msg.is_outbound),
            "is_read": bool(msg.is_read),
            "attachment_path": msg.attachment_path,
            "created_at": msg.created_at.isoformat() if msg.created_at else None
        })
    
    # 6. Получаем организацию
    org = None
    if contact.org_id:
        org_obj = db.query(Organization).filter(Organization.id == contact.org_id).first()
        if org_obj:
            org = {"id": org_obj.id, "name": org_obj.name, "is_vip": bool(org_obj.is_vip)}
    
    channels = []
    if contact.telegram_id:
        channels.append("telegram")
    if contact.email:
        channels.append("email")

    return {
        "contact": {
            "id": contact.id,
            "name": contact.name,
            "position": contact.position,
            "email": contact.email,
            "telegram_id": contact.telegram_id,
            "channels": channels,
            "organization": org
        },
        "messages": result_messages
    }


@app.post("/api/send")
async def send_message(req: SendMessageRequest, db: Session = Depends(get_db)):
    """
    SPEC-004: POST /api/send
    Единый метод отправки сообщения.
    
    Вход:
    - contact_id: ID контакта (для известных)
    - sender_id: прямой ID (для неразобранных)
    - channel: 'telegram' или 'email'
    - text: текст сообщения
    """
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    
    # 1. Определяем получателя
    recipient_id = None
    
    if req.contact_id:
        # Отправка через известный контакт
        contact = db.query(Contact).filter(Contact.id == req.contact_id).first()
        if not contact:
            raise HTTPException(status_code=404, detail=f"Contact {req.contact_id} not found")
        
        if req.channel == "telegram":
            if not contact.telegram_id:
                raise HTTPException(status_code=400, detail="Contact has no telegram_id")
            recipient_id = contact.telegram_id
        elif req.channel == "email":
            if not contact.email:
                raise HTTPException(status_code=400, detail="Contact has no email")
            recipient_id = contact.email
    
    elif req.sender_id:
        # Прямая отправка по sender_id (для неразобранных)
        recipient_id = req.sender_id
    
    else:
        raise HTTPException(status_code=400, detail="Either contact_id or sender_id must be provided")
    
    # 2. Отправляем сообщение
    if req.channel == "telegram":
        # 2a. Отправляем в Telegram
        if not TELEGRAM_BOT_TOKEN:
            raise HTTPException(status_code=500, detail="TELEGRAM_BOT_TOKEN not configured")
        
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = {
                "chat_id": recipient_id,
                "text": req.text
            }
            response = requests.post(url, json=payload, timeout=10)
            result = response.json()
            
            if not result.get("ok"):
                logger.error(f"Telegram send error: {result}")
                raise HTTPException(status_code=500, detail=f"Telegram error: {result.get('description')}")
            
            logger.info(f"✓ Telegram message sent to {recipient_id}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Telegram request error: {e}")
            raise HTTPException(status_code=500, detail=f"Network error: {e}")
    
    elif req.channel == "email":
        # 2b. Отправляем Email через SMTP
        EMAIL_SMTP_HOST = os.getenv("EMAIL_SMTP_HOST", "smtp.yandex.ru")
        EMAIL_SMTP_PORT = int(os.getenv("EMAIL_SMTP_PORT", "465"))
        EMAIL_SMTP_USER = os.getenv("EMAIL_SMTP_USER", EMAIL_IMAP_USER)
        EMAIL_SMTP_PASSWORD = os.getenv("EMAIL_SMTP_PASSWORD", EMAIL_IMAP_PASSWORD)
        
        if not EMAIL_SMTP_USER or not EMAIL_SMTP_PASSWORD:
            raise HTTPException(status_code=500, detail="Email SMTP credentials not configured")
        
        try:
            msg = MIMEMultipart()
            msg["From"] = EMAIL_SMTP_USER
            msg["To"] = recipient_id
            msg["Subject"] = "Сообщение от Anaconda"
            msg.attach(MIMEText(req.text, "plain", "utf-8"))
            
            with smtplib.SMTP_SSL(EMAIL_SMTP_HOST, EMAIL_SMTP_PORT) as server:
                server.login(EMAIL_SMTP_USER, EMAIL_SMTP_PASSWORD)
                server.send_message(msg)
            
            logger.info(f"✓ Email sent to {recipient_id}")
        except Exception as e:
            logger.error(f"Email send error: {e}")
            raise HTTPException(status_code=500, detail=f"Email error: {e}")
    
    else:
        raise HTTPException(status_code=400, detail=f"Unknown channel: {req.channel}")
    
    # 4. Сохраняем сообщение в БД как исходящее
    new_msg = Message(
        source=req.channel,
        sender="Anaconda",
        sender_id=recipient_id,
        text=req.text,
        is_outbound=True,
        is_read=True
    )
    db.add(new_msg)
    db.commit()
    db.refresh(new_msg)
    
    return {
        "status": "ok",
        "message_id": new_msg.id,
        "channel": req.channel,
        "recipient": recipient_id
    }


@app.post("/api/link_contact")
async def link_contact(request: Request, db: Session = Depends(get_db)):
    """
    SPEC-004: POST /api/link_contact
    Превращает "Неразобранное" в "Сотрудника".
    
    Вход: { "sender_id": "tg_555", "name": "Петр", "org_id": 1 }
    """
    data = await request.json()
    
    sender_id = data.get("sender_id")
    name = data.get("name")
    org_id = data.get("org_id")
    position = data.get("position", "")
    
    if not sender_id or not name or not org_id:
        raise HTTPException(status_code=400, detail="sender_id, name, and org_id are required")
    
    # 1. Определяем источник по sender_id (смотрим в messages)
    last_msg = db.query(Message).filter(Message.sender_id == sender_id).first()
    if not last_msg:
        raise HTTPException(status_code=404, detail=f"No messages found for sender_id={sender_id}")
    
    source = last_msg.source
    
    # 2. Проверяем организацию
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail=f"Organization {org_id} not found")
    
    # 3. Проверяем, не существует ли уже контакт
    existing = None
    if source == "email":
        existing = db.query(Contact).filter(Contact.email == sender_id).first()
    elif source == "telegram":
        existing = db.query(Contact).filter(Contact.telegram_id == sender_id).first()
    
    contact_id = None
    action = "created"
    
    if existing:
        existing.name = name
        existing.org_id = org_id
        if position:
            existing.position = position
        if source == "email":
            existing.email = sender_id
        elif source == "telegram":
            existing.telegram_id = sender_id
        contact_id = existing.id
        action = "updated"
        logger.info(f"✓ Contact updated: {name} -> {org.name}")
    else:
        # 4. Создаем новый контакт
        new_contact = Contact(
            name=name,
            position=position,
            org_id=org_id,
            email=sender_id if source == "email" else None,
            telegram_id=sender_id if source == "telegram" else None
        )
        db.add(new_contact)
        db.commit()
        db.refresh(new_contact)
        contact_id = new_contact.id
        logger.info(f"✓ Contact created: {name} ({source}={sender_id}) -> {org.name}")
    
    # 5. Обновляем contact_id во всех сообщениях этого отправителя
    if contact_id:
        db.query(Message).filter(
            Message.sender_id == sender_id
        ).update(
            {Message.contact_id: contact_id},
            synchronize_session=False
        )
        db.commit()
        logger.info(f"✓ Updated {db.query(Message).filter(Message.sender_id == sender_id).count()} messages with contact_id={contact_id}")
    
    return {
        "status": "ok",
        "action": action,
        "contact_id": contact_id,
        "organization": org.name
    }


# --- STARTUP/SHUTDOWN ---
@app.on_event("startup")
async def startup_event():
    """Запустить фоновые workers при старте приложения"""
    # Инициализация тестовых организаций
    db = SessionLocal()
    try:
        # Проверяем, есть ли организации
        orgs_count = db.query(Organization).count()
        if orgs_count == 0:
            org1 = Organization(name="Газпром", is_vip=True)
            org2 = Organization(name="Роснефть", is_vip=False)
            org3 = Organization(name="Сбербанк", is_vip=True)
            db.add_all([org1, org2, org3])
            db.commit()
            logger.info("✓ Test organizations created: Газпром, Роснефть, Сбербанк")
    finally:
        db.close()
    
    # Запускаем Telegram polling только если явно включен (TELEGRAM_USE_POLLING=true)
    # По умолчанию используется webhook
    if TELEGRAM_BOT_TOKEN and TELEGRAM_USE_POLLING:
        thread = threading.Thread(target=telegram_polling_worker, daemon=True)
        thread.start()
        logger.info("✓ Telegram polling thread started")
    elif TELEGRAM_BOT_TOKEN:
        logger.info("ℹ Telegram polling disabled (using webhook mode). Set TELEGRAM_USE_POLLING=true to enable polling.")
    
    if EMAIL_IMAP_USER and EMAIL_IMAP_PASSWORD:
        thread = threading.Thread(target=email_polling_worker, daemon=True)
        thread.start()
        logger.info("✓ Email IMAP polling thread started")

@app.on_event("shutdown")
async def shutdown_event():
    """Остановить фоновые workers при завершении"""
    global telegram_polling_active, email_polling_active
    telegram_polling_active = False
    email_polling_active = False
    logger.info("✓ All polling workers stopped")

