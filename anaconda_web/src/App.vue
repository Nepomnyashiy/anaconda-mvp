<script setup>
import { ref, onMounted, computed, nextTick } from 'vue'
import pkg from '../package.json'

// === STATE ===
const APP_VERSION = pkg.version || '1.0.0'

const chatData = ref({ unsorted: [], groups: [] })
const selectedChat = ref(null)
const selectedContact = ref(null)
const expandedGroups = ref([])
const showCreateContactModal = ref(false)
const showEditContactModal = ref(false)
const showOrgModal = ref(false)
const loading = ref(true)
const error = ref(null)

// Chat state
const messages = ref([])
const messageText = ref('')
const selectedChannel = ref('telegram')
const loadingMessages = ref(false)
const sendingMessage = ref(false)
const messagesContainer = ref(null)

// Organizations list
const organizations = ref([])

// Form states
const newContactForm = ref({
  name: '',
  position: '',
  sender_id: null,
  source: null,
  org_id: null,
  org_mode: 'existing',
  new_org_name: '',
  inn: ''
})

const selectedOrg = ref(null)

// === API URL ===
const getAPIUrl = () => {
  const configuredUrl = import.meta.env.VITE_API_URL?.replace(/\/$/, '')
  if (configuredUrl) return configuredUrl

  if (typeof window !== 'undefined') {
    const host = window.location.hostname
    if (host === 'localhost' || host === '127.0.0.1') {
      return 'http://localhost:8000/api'
    }
  }
  return '/api'
}

const API_URL = getAPIUrl()

// === COMPUTED ===
const isContactKnown = computed(() => {
  return selectedContact.value !== null
})

const availableChannels = computed(() => {
  if (!selectedContact.value) return []
  const channels = []
  if (selectedContact.value.telegram_id) channels.push('telegram')
  if (selectedContact.value.email) channels.push('email')
  return channels
})

// === METHODS ===

const fetchChats = async () => {
  try {
    const res = await fetch(`${API_URL}/hub_structure`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    
    // Преобразуем данные из нового формата SPEC-004
    chatData.value = {
      unsorted: data.unsorted || [],
      groups: (data.organizations || []).map(org => ({
        org_id: org.id,
        org_name: org.name,
        is_vip: org.is_vip,
        contacts: (org.contacts || []).map(contact => ({
          chat_id: `contact_${contact.id}`,
          contact_id: contact.id,
          display_name: contact.name,
          position: contact.position,
          source: contact.channels.includes('telegram') ? 'telegram' : 'email',
          unread: contact.unread_count,
          telegram_id: contact.channels.includes('telegram') ? 'has_telegram' : null,
          email: contact.channels.includes('email') ? 'has_email' : null,
          preview: contact.preview, // Добавлено согласно SPEC-004
          time: contact.time // Добавлено согласно SPEC-004
        })),
        total_unread: (org.contacts || []).reduce((sum, c) => sum + (c.unread_count || 0), 0),
        last_activity_ts: 0 // Это поле не используется в SPEC-004 для групп
      }))
    }
    error.value = null
  } catch (e) {
    error.value = `Ошибка загрузки диалогов: ${e.message}`
    console.error("Fetch chats error:", e)
  }
}

const fetchOrganizations = async () => {
  try {
    const res = await fetch(`${API_URL}/organizations`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    organizations.value = await res.json()
  } catch (e) {
    console.error("Fetch organizations error:", e)
  }
}

const fetchHistory = async (contactId) => {
  loadingMessages.value = true
  try {
    const res = await fetch(`${API_URL}/history/${contactId}`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    messages.value = data.messages || []
    selectedContact.value = data.contact
    
    // Устанавливаем канал по умолчанию
    if (data.contact.telegram_id) {
      selectedChannel.value = 'telegram'
    } else if (data.contact.email) {
      selectedChannel.value = 'email'
    }
    
    // Прокручиваем к последнему сообщению
    await nextTick()
    scrollToBottom()
  } catch (e) {
    console.error("Fetch history error:", e)
    messages.value = []
  } finally {
    loadingMessages.value = false
  }
}

const scrollToBottom = () => {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

const toggleGroup = (orgId) => {
  if (expandedGroups.value.includes(orgId)) {
    expandedGroups.value = expandedGroups.value.filter(id => id !== orgId)
  } else {
    expandedGroups.value.push(orgId)
  }
}

const selectChat = async (chat) => {
  selectedChat.value = chat
  messages.value = []
  selectedContact.value = null
  
  // Если есть contact_id (известный контакт), загружаем историю
  if (chat.contact_id) {
    await fetchHistory(chat.contact_id)
  } else {
    // Для неразобранных - загружаем по sender_id
    await fetchMessagesBySender(chat.sender_id, chat.source)
  }
}

const fetchMessagesBySender = async (senderId, source) => {
  loadingMessages.value = true
  try {
    const res = await fetch(`${API_URL}/messages/by_sender/${encodeURIComponent(senderId)}`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    
    messages.value = data.messages || []
    
    // Создаем "псевдо-контакт" для неразобранных
    selectedContact.value = {
      id: null,
      sender_id: senderId,
      source: source,
      name: data.sender_info.display_name
    }
    
    selectedChannel.value = source
    
    await nextTick()
    scrollToBottom()
  } catch (e) {
    console.error("Fetch messages error:", e)
    messages.value = []
  } finally {
    loadingMessages.value = false
  }
}

const selectKnownContact = async (contact, orgName) => {
  selectedChat.value = {
    chat_id: `contact_${contact.id}`,
    display_name: contact.name,
    position: contact.position,
    org_name: orgName,
    contact_id: contact.id
  }
  await fetchHistory(contact.id)
}

const backToHub = () => {
  selectedChat.value = null
  selectedContact.value = null
  messages.value = []
}

const openCreateContactModal = () => {
  if (!selectedChat.value) return
  newContactForm.value = {
    name: selectedChat.value.display_name || '',
    position: '',
    sender_id: selectedChat.value.sender_id,
    source: selectedChat.value.source,
    org_id: null,
    org_mode: 'existing',
    new_org_name: '',
    inn: ''
  }
  showCreateContactModal.value = true
}

const linkContact = async () => {
  if (!newContactForm.value.name?.trim()) {
    alert('Укажите имя')
    return
  }

  let targetOrgId = null
  let orgNameForChat = null
  const mode = newContactForm.value.org_mode

  if (mode === 'existing') {
    if (!newContactForm.value.org_id) {
      alert('Выберите существующую организацию')
      return
    }
    targetOrgId = newContactForm.value.org_id
    orgNameForChat = organizations.value.find(org => org.id === targetOrgId)?.name || ''
  } else if (mode === 'new') {
    if (!newContactForm.value.new_org_name?.trim()) {
      alert('Укажите название новой организации')
      return
    }
    try {
      const orgPayload = {
        name: newContactForm.value.new_org_name.trim(),
        inn: newContactForm.value.inn || null
      }
      const resOrg = await fetch(`${API_URL}/organizations`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(orgPayload)
      })
      const dataOrg = await resOrg.json()
      if (!resOrg.ok) {
        throw new Error(dataOrg.detail || dataOrg.message || 'Ошибка создания организации')
      }
      targetOrgId = dataOrg.id
      orgNameForChat = dataOrg.name
      await fetchOrganizations()
    } catch (e) {
      alert(`Ошибка создания организации: ${e.message}`)
      return
    }
  } else {
    alert('Выберите режим привязки к организации')
    return
  }

  try {
    const payload = {
      sender_id: newContactForm.value.sender_id,
      name: newContactForm.value.name.trim(),
      position: newContactForm.value.position,
      org_id: targetOrgId
    }

    const res = await fetch(`${API_URL}/link_contact`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })

    const data = await res.json()

    if (!res.ok) {
      throw new Error(data.detail || data.message || 'Ошибка привязки контакта')
    }

    console.log('✓ Contact linked:', data)
    showCreateContactModal.value = false
    
    await fetchChats()
    if (data.contact_id) {
      await fetchHistory(data.contact_id)
      selectedChat.value = {
        ...selectedChat.value,
        contact_id: data.contact_id,
        org_name: orgNameForChat || data.organization || selectedChat.value?.org_name
      }
    }
  } catch (e) {
    alert(`Ошибка: ${e.message}`)
  }
}

const openEditContactModal = () => {
  if (!selectedContact.value) return
  alert('Редактирование контакта будет реализовано позже')
}


const sendMessage = async () => {
  if (!messageText.value.trim() || !selectedContact.value) return
  if (sendingMessage.value) return
  
  sendingMessage.value = true
  
  try {
    // Формируем payload в зависимости от типа контакта
    const payload = selectedContact.value.id 
      ? {
          // Для известных контактов
          contact_id: selectedContact.value.id,
          channel: selectedChannel.value,
          text: messageText.value.trim()
        }
      : {
          // Для неразобранных контактов
          sender_id: selectedContact.value.sender_id,
          channel: selectedContact.value.source,
          text: messageText.value.trim()
        }

    const res = await fetch(`${API_URL}/send`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })

    const data = await res.json()

    if (!res.ok) {
      throw new Error(data.detail || 'Ошибка отправки')
    }

    console.log('✓ Message sent:', data)
    
    // Добавляем сообщение в список
    messages.value.push({
      id: data.message_id,
      source: selectedContact.value.source || selectedChannel.value,
      text: messageText.value.trim(),
      is_outbound: true,
      is_read: true,
      created_at: new Date().toISOString()
    })
    
    messageText.value = ''
    
    await nextTick()
    scrollToBottom()
  } catch (e) {
    alert(`Ошибка отправки: ${e.message}`)
  } finally {
    sendingMessage.value = false
  }
}

const openOrgModal = (org) => {
  selectedOrg.value = org
  showOrgModal.value = true
}

const formatTime = (isoString) => {
  if (!isoString) return ''
  const date = new Date(isoString)
  return date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
}

const formatDate = (isoString) => {
  if (!isoString) return ''
  const date = new Date(isoString)
  return date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
}

// === LIFECYCLE ===

onMounted(async () => {
  try {
    await Promise.all([fetchChats(), fetchOrganizations()])
  } finally {
    loading.value = false
  }

  // Периодически обновляем
  setInterval(() => {
    fetchChats()
  }, 5000)
})

// === COLOR HELPERS ===
const getSourceColor = (source) => {
  return source === 'telegram' ? 'bg-sky-500' : 'bg-red-500'
}

const getSourceIcon = (source) => {
  return source === 'telegram' ? 'fa-brands fa-telegram' : 'fa-solid fa-envelope'
}

const getSourceBorderColor = (source, isOutbound) => {
  if (isOutbound) return 'border-l-green-500'
  return source === 'telegram' ? 'border-l-sky-500' : 'border-l-red-500'
}
</script>

<template>
  <div class="flex h-screen overflow-hidden bg-slate-50">

    <!-- SIDEBAR -->
    <div :class="[
      'w-full md:w-96 flex flex-col bg-white border-r border-slate-200 h-full transition-all',
      selectedChat ? 'hidden md:flex' : 'flex'
    ]">

      <!-- Header -->
      <div class="p-4 bg-gradient-to-r from-blue-900 to-slate-900 text-white flex justify-between items-center">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 bg-white/20 rounded-full flex items-center justify-center">
            <i class="fa-solid fa-comments text-xl"></i>
          </div>
          <div>
            <h1 class="font-bold text-xl tracking-tight">КИП-СЕРВИС</h1>
            <p class="text-xs text-blue-200 opacity-80">Единое окно продаж</p>
          </div>
        </div>
        <div class="flex items-center gap-3">
          <span v-if="chatData.unsorted.length > 0" 
                class="text-xs bg-red-600 px-2 py-1 rounded-full animate-pulse">
            {{ chatData.unsorted.length }} новых
          </span>
          <span class="text-xs bg-blue-700 px-2 py-1 rounded-full">
            v{{ APP_VERSION }}
          </span>
        </div>
      </div>

      <!-- Unsorted Section -->
      <div class="flex-1 overflow-y-auto">
        <div v-if="loading" class="p-4 text-slate-500 text-sm">Загрузка...</div>
        <div v-else-if="error" class="p-4 text-red-600 text-sm">{{ error }}</div>

        <div v-if="chatData.unsorted.length" class="mb-2">
          <div class="px-4 py-2 text-xs font-bold text-red-600 uppercase tracking-wider bg-red-50">
            📥 Неразобранное
          </div>
          <div v-for="chat in chatData.unsorted" :key="chat.chat_id"
               @click="selectChat(chat)"
               class="p-3 border-b hover:bg-red-50 cursor-pointer border-l-4 border-l-red-500">
            <div class="flex items-center gap-2">
              <div class="w-8 h-8 rounded-full flex items-center justify-center text-white text-xs"
                   :class="getSourceColor(chat.source)">
                <i :class="getSourceIcon(chat.source)"></i>
              </div>
              <div class="flex-1 min-w-0">
                <div class="font-bold text-red-700 truncate">{{ chat.display_name }}</div>
                <div class="text-xs text-slate-500 truncate">{{ chat.last_message }}</div>
              </div>
            </div>
          </div>
        </div>

        <!-- Groups Section -->
        <div v-for="group in chatData.groups" :key="group.org_id" class="border-b border-slate-100">

          <!-- Group Header -->
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

          <!-- Contacts in Group -->
          <div v-if="expandedGroups.includes(group.org_id)" class="bg-white">
            <div v-for="chat in group.contacts" :key="chat.chat_id"
                 @click="selectKnownContact({ id: chat.contact_id || chat.id, name: chat.display_name, position: chat.position, telegram_id: chat.telegram_id, email: chat.email }, group.org_name)"
                 class="p-3 pl-8 border-b border-slate-50 hover:bg-sky-50 cursor-pointer flex items-center gap-3 transition-colors"
                 :class="selectedChat?.chat_id === chat.chat_id ? 'bg-blue-50' : ''">

              <div class="w-8 h-8 rounded-full flex items-center justify-center text-white text-xs shadow-sm flex-shrink-0"
                   :class="getSourceColor(chat.source)">
                <i :class="getSourceIcon(chat.source)"></i>
              </div>

              <div class="min-w-0 flex-1">
                <div class="font-bold text-sm text-slate-800">{{ chat.display_name }}</div>
                <div class="text-xs text-slate-500">{{ chat.position }}</div>
              </div>

              <div v-if="chat.unread > 0" class="text-xs font-bold text-red-600 flex-shrink-0">
                {{ chat.unread }}
              </div>
            </div>
          </div>

        </div>
      </div>
    </div>

    <!-- CHAT AREA -->
    <div :class="[
      'flex-1 flex-col bg-slate-100 relative h-full',
      selectedChat ? 'flex fixed inset-0 z-50 md:static' : 'hidden md:flex'
    ]">

      <!-- Empty State -->
      <div v-if="!selectedChat" class="hidden md:flex items-center justify-center h-full text-slate-400">
        <div class="text-center">
          <i class="fa-solid fa-comments text-6xl mb-4"></i>
          <p>Выберите диалог из списка</p>
        </div>
      </div>

      <!-- Chat Header -->
      <div v-else class="h-16 bg-white border-b shadow-sm flex items-center px-4 justify-between shrink-0">
        <div class="flex items-center gap-3">
          <button @click="backToHub" class="md:hidden w-8 h-8 flex items-center justify-center text-slate-600">
            <i class="fa-solid fa-arrow-left"></i>
          </button>

          <div>
            <div class="font-bold text-slate-800 leading-tight">{{ selectedChat.display_name }}</div>
            <div v-if="selectedContact?.organization" class="text-xs text-blue-600 font-semibold cursor-pointer hover:underline">
              {{ selectedContact.position }} | {{ selectedContact.organization.name }}
            </div>
            <div v-else-if="selectedChat.org_name" class="text-xs text-blue-600 font-semibold">
              {{ selectedChat.position }} | {{ selectedChat.org_name }}
            </div>
            <div v-else class="text-xs text-red-500 font-bold">⚠ Неизвестный контакт</div>
          </div>
        </div>

        <!-- Action Buttons -->
        <div class="flex gap-2">
          <button v-if="!isContactKnown"
                  @click="openCreateContactModal"
                  class="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 transition font-semibold text-sm">
            <i class="fa-solid fa-user-plus mr-1"></i> Привязать
          </button>
          <button v-else
                  @click="openEditContactModal"
                  class="px-3 py-2 bg-slate-200 text-slate-700 rounded hover:bg-slate-300 transition text-sm"
                  title="Редактировать контакт">
            <i class="fa-solid fa-pencil"></i>
          </button>
        </div>
      </div>

      <!-- Messages Area -->
      <div v-if="selectedChat" ref="messagesContainer" class="flex-1 overflow-y-auto p-4 bg-[#e5ddd5]/30">
        
        <!-- Loading -->
        <div v-if="loadingMessages" class="text-center py-10 text-slate-500">
          <i class="fa-solid fa-spinner fa-spin text-2xl"></i>
          <p class="mt-2">Загрузка истории...</p>
        </div>
        
        <!-- No messages -->
        <div v-else-if="messages.length === 0" class="text-center py-10 text-slate-500">
          <i class="fa-solid fa-inbox text-4xl mb-2"></i>
          <p>Нет сообщений</p>
        </div>
        
        <!-- Messages list -->
        <div v-else class="space-y-2">
          <div v-for="msg in messages" :key="msg.id"
               :class="[
                 'max-w-[80%] p-3 rounded-lg border-l-4 shadow-sm',
                 msg.is_outbound 
                   ? 'ml-auto bg-green-100 border-l-green-500' 
                   : 'mr-auto bg-white',
                 getSourceBorderColor(msg.source, msg.is_outbound)
               ]">
            
            <!-- Source indicator -->
            <div class="flex items-center gap-2 mb-1">
              <div class="w-4 h-4 rounded-full flex items-center justify-center text-white text-[8px]"
                   :class="getSourceColor(msg.source)">
                <i :class="getSourceIcon(msg.source)"></i>
              </div>
              <span class="text-[10px] text-slate-400">
                {{ msg.source === 'telegram' ? 'Telegram' : 'Email' }}
                <span v-if="msg.is_outbound" class="text-green-600">• Исходящее</span>
              </span>
            </div>
            
            <!-- Message text -->
            <div class="text-sm text-slate-800 whitespace-pre-wrap">{{ msg.text }}</div>
            
            <!-- Time -->
            <div class="text-[10px] text-slate-400 text-right mt-1">
              {{ formatDate(msg.created_at) }} {{ formatTime(msg.created_at) }}
              <i v-if="msg.is_read" class="fa-solid fa-check-double text-blue-500 ml-1"></i>
            </div>
          </div>
        </div>
      </div>

      <!-- Message Input -->
      <div v-if="selectedChat && selectedContact" class="bg-white p-2 border-t shrink-0">
        <!-- Channel selector (только для известных контактов с несколькими каналами) -->
        <div v-if="selectedContact.id && availableChannels.length > 1" class="flex items-center gap-2 mb-2 px-2">
          <span class="text-xs text-slate-500">Ответить в:</span>
          <button v-for="ch in availableChannels" :key="ch"
                  @click="selectedChannel = ch"
                  :class="[
                    'px-3 py-1 rounded-full text-xs font-semibold transition',
                    selectedChannel === ch 
                      ? (ch === 'telegram' ? 'bg-sky-500 text-white' : 'bg-red-500 text-white')
                      : 'bg-slate-200 text-slate-600 hover:bg-slate-300'
                  ]">
            <i :class="getSourceIcon(ch)" class="mr-1"></i>
            {{ ch === 'telegram' ? 'Telegram' : 'Email' }}
          </button>
        </div>
        
        <!-- Информация о канале для неразобранных -->
        <div v-else-if="!selectedContact.id" class="text-xs text-slate-500 mb-2 px-2">
          Ответить в: <i :class="getSourceIcon(selectedContact.source)" class="mr-1"></i>
          {{ selectedContact.source === 'telegram' ? 'Telegram' : 'Email' }}
        </div>
        
        <!-- Input -->
        <div class="flex items-center gap-2">
          <button class="p-3 text-slate-400 hover:text-slate-600" title="Прикрепить файл">
            <i class="fa-solid fa-paperclip"></i>
          </button>
          <input v-model="messageText"
                 @keyup.enter="sendMessage"
                 :disabled="sendingMessage"
                 class="flex-1 bg-slate-100 rounded-full py-2 px-4 focus:outline-none focus:ring-2 focus:ring-blue-500"
                 placeholder="Введите сообщение..." />
          <button @click="sendMessage" 
                  :disabled="sendingMessage || !messageText.trim()"
                  class="p-3 text-blue-600 hover:text-blue-700 disabled:text-slate-300">
            <i v-if="sendingMessage" class="fa-solid fa-spinner fa-spin text-xl"></i>
            <i v-else class="fa-solid fa-paper-plane text-xl"></i>
          </button>
        </div>
      </div>

    </div>

    <!-- LINK CONTACT MODAL (SPEC-004) -->
    <div v-if="showCreateContactModal" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div class="bg-white rounded-lg p-6 max-w-md w-full mx-4">
        <h3 class="text-xl font-bold mb-4">
          <i class="fa-solid fa-user-plus text-blue-600 mr-2"></i>
          Привязать контакт
        </h3>

        <div class="space-y-4">
          <!-- Name -->
          <div>
            <label class="block text-sm font-semibold mb-1">ФИО *</label>
            <input v-model="newContactForm.name" type="text" 
                   class="w-full border border-slate-300 rounded px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
          </div>

          <!-- Position -->
          <div>
            <label class="block text-sm font-semibold mb-1">Должность</label>
            <input v-model="newContactForm.position" type="text" 
                   class="w-full border border-slate-300 rounded px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
          </div>

          <!-- Organization Selection -->
          <div>
            <label class="block text-sm font-semibold mb-1">Организация *</label>
            <select v-model="newContactForm.org_id" 
                    class="w-full border border-slate-300 rounded px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
              <option :value="null">-- Выберите организацию --</option>
              <option v-for="org in organizations" :key="org.id" :value="org.id">
                {{ org.name }}
                <span v-if="org.is_vip">👑</span>
              </option>
            </select>
          </div>

          <!-- Source info -->
          <div class="bg-slate-50 rounded p-3 text-sm text-slate-600">
            <p><strong>Источник:</strong> {{ newContactForm.source === 'telegram' ? 'Telegram' : 'Email' }}</p>
            <p><strong>ID:</strong> {{ newContactForm.sender_id }}</p>
          </div>

          <!-- Buttons -->
          <div class="flex gap-3 pt-4">
            <button @click="showCreateContactModal = false"
                    class="flex-1 px-4 py-2 bg-slate-300 text-slate-900 rounded hover:bg-slate-400 font-semibold">
              Отмена
            </button>
            <button @click="linkContact"
                    :disabled="!newContactForm.name || !newContactForm.org_id"
                    class="flex-1 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 font-semibold disabled:bg-slate-300 disabled:cursor-not-allowed">
              <i class="fa-solid fa-link mr-1"></i> Привязать
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- ORGANIZATION INFO MODAL -->
    <div v-if="showOrgModal && selectedOrg" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div class="bg-white rounded-lg p-6 max-w-md w-full mx-4">
        <h3 class="text-xl font-bold mb-4 flex items-center gap-2">
          <i class="fa-solid fa-building text-slate-600"></i>
          {{ selectedOrg.org_name }}
          <i v-if="selectedOrg.is_vip" class="fa-solid fa-crown text-yellow-500"></i>
        </h3>

        <div class="space-y-3 mb-6">
          <div>
            <p class="text-xs text-slate-500 uppercase">Контактов в системе</p>
            <p class="font-semibold">{{ selectedOrg.contacts?.length || 0 }}</p>
          </div>
          <div>
            <p class="text-xs text-slate-500 uppercase">Непрочитанных сообщений</p>
            <p class="font-semibold">{{ selectedOrg.total_unread || 0 }}</p>
          </div>
        </div>

        <button @click="showOrgModal = false"
                class="w-full px-4 py-2 bg-slate-300 text-slate-900 rounded hover:bg-slate-400">
          Закрыть
        </button>
      </div>
    </div>

  </div>
</template>

<style scoped>
/* Custom scrollbar */
::-webkit-scrollbar {
  width: 6px;
}
::-webkit-scrollbar-track {
  background: #f1f5f9;
}
::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover {
  background: #94a3b8;
}
</style>
