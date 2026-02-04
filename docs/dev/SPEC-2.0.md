# ТЕХНИЧЕСКАЯ СПЕЦИФИКАЦИЯ v2.0

**Модуль:** Организационная структура чатов (Account-Based Chat)
**Цель:** Группировка коммуникаций по Компаниям, управление иерархией «Организация -> Сотрудники», полная мобильная адаптация.

---

## 1. БЭКЕНД: Архитектура Данных и Логика

Мы используем существующий стек (**FastAPI + SQLAlchemy**). Нам нужно расширить модели, чтобы поддерживать жесткую связку.

### 1.1. Схема БД (SQLAlchemy Models)

Необходимо убедиться, что модели `models.py` поддерживают следующие связи:

```python
class Organization(Base):
    __tablename__ = "organizations"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, index=True) # Напр. "ПАО Газпром"
    inn = Column(String, nullable=True)            # Для проверки дублей
    is_vip = Column(Boolean, default=False)        # Метка VIP (Корона)
    
    # Связь: Одна компания -> Много сотрудников
    contacts = relationship("Contact", back_populates="org")

class Contact(Base):
    __tablename__ = "contacts"
    id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=True) # Привязка
    
    # Персональные данные
    name = Column(String)       # "Иванов Иван"
    position = Column(String)   # "Главный инженер"
    
    # Ключи связи (Identity Keys)
    email = Column(String, unique=True, index=True)
    telegram_id = Column(String, unique=True, index=True)

    org = relationship("Organization", back_populates="contacts")

```

### 1.2. API: Новая логика выдачи чатов (`GET /api/chats`)

Мы меняем формат ответа. Вместо «плоского списка» мы отдаем **Иерархическое дерево**.

**Алгоритм для Бэкенда:**

1. Получить список всех последних сообщений, сгруппированных по `sender_id`.
2. Для каждого `sender_id` найти Контакт.
3. Если Контакт привязан к Организации -> Добавить его в бакет этой Организации.
4. Если Контакт не найден или нет Организации -> Добавить в бакет "Неразобранное".

**JSON Response (Спецификация):**

```json
{
  "unsorted": [  // Блок "Неразобранное" (Всегда сверху)
    {
      "chat_id": "tg_12345",
      "source": "telegram",
      "display_name": "User 777",
      "last_message": "Здравствуйте...",
      "unread": 1
    }
  ],
  "groups": [    // Блок Компаний (Сортировка по активности)
    {
      "org_id": 10,
      "org_name": "ПАО Газпром",
      "is_vip": true,
      "total_unread": 5,
      "last_activity_ts": 1700000000,
      "contacts": [  // Список чатов внутри папки
        {
          "chat_id": "email_ivanov@gazprom.ru",
          "source": "email",
          "display_name": "Иванов И.И.",
          "position": "Нач. закупки",
          "unread": 2
        },
        {
          "chat_id": "tg_999888",
          "source": "telegram",
          "display_name": "Петров (Инженер)",
          "position": "КИПиА",
          "unread": 3
        }
      ]
    },
    {
      "org_id": 12,
      "org_name": "Роснефть",
      // ...
    }
  ]
}

```

### 1.3. API: Создание связи (`POST /api/contacts`)

Когда мы создаем контакт из чата, мы должны уметь **создать новую организацию на лету** или выбрать существующую.

**Input JSON:**

```json
{
  "sender_id": "tg_12345",  // Кого привязываем
  "name": "Сидоров Петр",
  "position": "Менеджер",
  "org_mode": "existing",   // или "new"
  "org_id": 10,             // Если existing
  "new_org_name": null      // Если new (создаст Org в БД и вернет ID)
}

```

---

## 2. ФРОНТЕНД: UX/UI и Мобильная Адаптация

Мы реализуем интерфейс **Master-Detail** с адаптивностью через CSS (Tailwind).

### 2.1. Логика Адаптивности (Responsive State)

Используем одну переменную состояния `selectedChat`.

| Состояние | Desktop (>768px) | Mobile (<768px) |
| --- | --- | --- |
| **Чат не выбран** | Слева список, справа заглушка. | На весь экран список (Hub). |
| **Чат выбран** | Слева список, справа чат. | На весь экран Чат. Список скрыт. |

### 2.2. Компонент: Сайдбар (Список Компаний)

Это «Аккордеон».

* **Header Группы (Компания):**
* Высота 50px. Фон светло-серый (`bg-slate-100`).
* При клике: Раскрывается/Сворачивается список сотрудников.
* Индикатор: Если свернуто, показываем бейдж с суммой непрочитанных (красный кружок).


* **Элемент Списка (Сотрудник):**
* Сдвинут вправо (отступ иерархии).
* Цветовая полоска слева: Синяя (TG) или Красная (Email).



### 2.3. Компонент: Карточка Сотрудника (Внутри чата)

В верхней части чата (Header) мы делаем не просто текст, а интерактивную панель.

**Макет Header'а:**

```
[< Назад]  [ Аватар ]  [ Имя Фамилия      ]   [Действия]
(Mobile)               [ Должность | Орг. ]

```

* **Название Организации:** Должно быть кликабельным. При клике открывается модалка "Информация о компании" (адрес, реквизиты, все контакты).
* **Кнопка действий (Mobile):** Три точки `⋮` -> Выпадающее меню: "Создать сделку", "Позвонить", "Переслать в ERP".

---

## 3. Спецификация Интерфейса (Vue.js Код)

Ниже приведен «скелет» компонента `App.vue`, реализующий эту логику.

```html
<script setup>
import { ref, computed } from 'vue'

// --- STATE ---
const chatData = ref({ unsorted: [], groups: [] }) // Данные с бэкенда
const selectedChat = ref(null) // Текущий активный чат
const expandedGroups = ref([]) // ID раскрытых компаний

// --- ACTIONS ---
const toggleGroup = (orgId) => {
  if (expandedGroups.value.includes(orgId)) {
    expandedGroups.value = expandedGroups.value.filter(id => id !== orgId)
  } else {
    expandedGroups.value.push(orgId)
  }
}

const selectChat = (chat) => {
  selectedChat.value = chat
  // На мобильном это действие автоматически скроет список и покажет чат
  // благодаря CSS классам (см. ниже)
}

const backToHub = () => {
  selectedChat.value = null // Возврат к списку (для Mobile)
}
</script>

<template>
  <div class="flex h-screen overflow-hidden bg-slate-50">

    <div :class="[
      'w-full md:w-96 flex flex-col bg-white border-r border-slate-200 h-full transition-all',
      selectedChat ? 'hidden md:flex' : 'flex'
    ]">
      
      <div class="p-4 bg-slate-900 text-white md:hidden flex justify-between items-center">
        <h1 class="font-bold text-lg">Anaconda Hub</h1>
        <span class="text-xs bg-red-600 px-2 rounded-full">3 new</span>
      </div>

      <div class="flex-1 overflow-y-auto">
        <div v-if="chatData.unsorted.length" class="mb-2">
           <div class="px-4 py-2 text-xs font-bold text-slate-400 uppercase tracking-wider">Неразобранное</div>
           <div v-for="chat in chatData.unsorted" :key="chat.chat_id"
                @click="selectChat(chat)"
                class="p-3 border-b hover:bg-slate-50 cursor-pointer border-l-4 border-red-500 bg-red-50/30">
             <div class="font-bold text-red-700">{{ chat.display_name }}</div>
             <div class="text-xs text-slate-500 truncate">{{ chat.last_message }}</div>
           </div>
        </div>

        <div v-for="group in chatData.groups" :key="group.org_id" class="border-b border-slate-100">
          
          <div @click="toggleGroup(group.org_id)" 
               class="p-3 bg-slate-50 flex justify-between items-center cursor-pointer hover:bg-slate-100 select-none">
            <div class="flex items-center gap-2">
              <i class="fa-solid fa-building text-slate-400"></i>
              <span class="font-bold text-slate-700">{{ group.org_name }}</span>
              <i v-if="group.is_vip" class="fa-solid fa-crown text-yellow-500 text-xs"></i>
            </div>
            <div class="flex items-center gap-2">
               <span v-if="!expandedGroups.includes(group.org_id) && group.total_unread > 0" 
                     class="bg-blue-600 text-white text-xs font-bold px-2 py-0.5 rounded-full">
                 {{ group.total_unread }}
               </span>
               <i class="fa-solid text-slate-400 text-xs transition-transform"
                  :class="expandedGroups.includes(group.org_id) ? 'fa-chevron-up' : 'fa-chevron-down'"></i>
            </div>
          </div>

          <div v-if="expandedGroups.includes(group.org_id)" class="bg-white">
            <div v-for="chat in group.contacts" :key="chat.chat_id"
                 @click="selectChat(chat)"
                 class="p-3 pl-8 border-b border-slate-50 hover:bg-sky-50 cursor-pointer flex items-center gap-3 transition-colors"
                 :class="selectedChat?.chat_id === chat.chat_id ? 'bg-blue-50' : ''">
              
              <div class="w-8 h-8 rounded-full flex items-center justify-center text-white text-xs shadow-sm flex-shrink-0"
                   :class="chat.source === 'telegram' ? 'bg-sky-500' : 'bg-red-500'">
                <i :class="chat.source === 'telegram' ? 'fa-brands fa-telegram' : 'fa-solid fa-envelope'"></i>
              </div>

              <div class="min-w-0">
                <div class="font-bold text-sm text-slate-800">{{ chat.display_name }}</div>
                <div class="text-xs text-slate-500">{{ chat.position }}</div>
              </div>
            </div>
          </div>

        </div>
      </div>
    </div>

    <div :class="[
       'flex-1 flex-col bg-slate-100 relative h-full',
       selectedChat ? 'flex fixed inset-0 z-50 md:static' : 'hidden md:flex'
    ]">
      
      <div v-if="!selectedChat" class="hidden md:flex items-center justify-center h-full text-slate-400">
         Выберите диалог из списка
      </div>

      <div v-else class="flex flex-col h-full w-full">
         
         <div class="h-16 bg-white border-b shadow-sm flex items-center px-4 justify-between shrink-0">
            <div class="flex items-center gap-3">
               <button @click="backToHub" class="md:hidden w-8 h-8 flex items-center justify-center text-slate-600">
                 <i class="fa-solid fa-arrow-left"></i>
               </button>

               <div>
                 <div class="font-bold text-slate-800 leading-tight">{{ selectedChat.display_name }}</div>
                 <div v-if="selectedChat.org_name" class="text-xs text-blue-600 font-semibold cursor-pointer hover:underline">
                    {{ selectedChat.org_name }}
                 </div>
                 <div v-else class="text-xs text-red-500 font-bold">Неизвестный контакт</div>
               </div>
            </div>

            <button class="w-10 h-10 bg-slate-100 rounded-full hover:bg-slate-200 text-slate-600">
               <i class="fa-solid fa-ellipsis-vertical"></i>
            </button>
         </div>

         <div class="flex-1 overflow-y-auto p-4 bg-[#e5ddd5]/30">
            </div>

         <div class="bg-white p-2 border-t flex items-center gap-2 shrink-0 safe-area-bottom">
            <button class="p-3 text-slate-400"><i class="fa-solid fa-paperclip"></i></button>
            <input class="flex-1 bg-slate-100 rounded-full py-2 px-4 focus:outline-none focus:ring-2 focus:ring-blue-500" 
                   placeholder="Сообщение..." />
            <button class="p-3 text-blue-600"><i class="fa-solid fa-paper-plane text-xl"></i></button>
         </div>

      </div>
    </div>

  </div>
</template>

```

---

## 4. План реализации

Эта спецификация закрывает все ваши требования. Она сложная внутри (Бэкенд), но простая снаружи для менеджера.

**Шаги для разработчика:**

1. **DB Migration:** Проверить, что в таблице `contacts` есть `org_id` (уже есть, но проверить индексы).
2. **API Refactor:** Переписать `get_chats` на Python, чтобы он собирал иерархический JSON (группы + списки).
3. **Frontend Layout:** Внедрить адаптивный `v-if/hidden md:flex` (как в коде выше).
4. **Components:** Реализовать логику раскрытия аккордеона.

 - *Ссылки на ТЗ Anaconda (Архитектура, Слои, Связывание данных, Аналитика)*