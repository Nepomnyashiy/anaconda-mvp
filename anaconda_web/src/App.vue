<script setup>
import { ref, onMounted, computed } from 'vue'

// === STATE ===
const chatData = ref({ unsorted: [], groups: [] })
const selectedChat = ref(null)
const expandedGroups = ref([])
const showCreateContactModal = ref(false)
const showOrgModal = ref(false)
const loading = ref(true)
const error = ref(null)

// Form states
const newContactForm = ref({
  name: '',
  position: '',
  sender_id: null,
  source: null,
  org_mode: null,
  org_id: null,
  new_org_name: null,
  inn: null
})

const selectedOrg = ref(null)

// === API URL ===
const getAPIUrl = () => {
  if (typeof window !== 'undefined') {
    const host = window.location.hostname
    if (host === 'localhost' || host === '127.0.0.1') {
      return 'http://localhost:8000/api'
    }
    return `http://${host}:8000/api`
  }
  return '/api'
}

const API_URL = getAPIUrl()

// === COMPUTED ===
const isContactKnown = computed(() => {
  return selectedChat.value?.position !== undefined && selectedChat.value?.position !== null
})

// === METHODS ===

const fetchChats = async () => {
  try {
    const res = await fetch(`${API_URL}/chats`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    chatData.value = data
    error.value = null
  } catch (e) {
    error.value = `Ошибка загрузки диалогов: ${e.message}`
    console.error("Fetch chats error:", e)
  }
}

const toggleGroup = (orgId) => {
  if (expandedGroups.value.includes(orgId)) {
    expandedGroups.value = expandedGroups.value.filter(id => id !== orgId)
  } else {
    expandedGroups.value.push(orgId)
  }
}

const selectChat = (chat) => {
  selectedChat.value = chat
}

const backToHub = () => {
  selectedChat.value = null
}

const openCreateContactModal = () => {
  if (!selectedChat.value) return
  newContactForm.value = {
    name: selectedChat.value.display_name || '',
    position: selectedChat.value.position || '',
    sender_id: selectedChat.value.sender_id,
    source: selectedChat.value.source,
    org_mode: null,
    org_id: null,
    new_org_name: null,
    inn: null
  }
  showCreateContactModal.value = true
}

const createContact = async () => {
  if (!newContactForm.value.name) {
    alert('Укажите имя контакта')
    return
  }

  if (!newContactForm.value.org_mode) {
    alert('Выберите режим работы с организацией')
    return
  }

  try {
    const payload = {
      name: newContactForm.value.name,
      position: newContactForm.value.position,
      sender_id: newContactForm.value.sender_id,
      source: newContactForm.value.source,
      org_mode: newContactForm.value.org_mode
    }

    if (newContactForm.value.org_mode === 'existing') {
      payload.org_id = newContactForm.value.org_id
    } else if (newContactForm.value.org_mode === 'new') {
      payload.new_org_name = newContactForm.value.new_org_name
      payload.inn = newContactForm.value.inn
    }

    const res = await fetch(`${API_URL}/contacts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })

    const data = await res.json()

    if (!res.ok) {
      throw new Error(data.message || 'Ошибка создания контакта')
    }

    console.log('✓ Contact created:', data)
    showCreateContactModal.value = false
    await fetchChats()

    // Перевыбираем диалог
    if (selectedChat.value) {
      const group = chatData.value.groups.find(g =>
        g.contacts.some(c => c.sender_id === selectedChat.value.sender_id)
      )
      if (group) {
        const updated = group.contacts.find(c => c.sender_id === selectedChat.value.sender_id)
        if (updated) {
          selectedChat.value = updated
        }
      }
    }
  } catch (e) {
    alert(`Ошибка: ${e.message}`)
  }
}

const openOrgModal = (org) => {
  selectedOrg.value = org
  showOrgModal.value = true
}

// === LIFECYCLE ===

onMounted(async () => {
  try {
    await fetchChats()
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
</script>

<template>
  <div class="flex h-screen overflow-hidden bg-slate-50">

    <!-- SIDEBAR -->
    <div :class="[
      'w-full md:w-96 flex flex-col bg-white border-r border-slate-200 h-full transition-all',
      selectedChat ? 'hidden md:flex' : 'flex'
    ]">

      <!-- Mobile Header -->
      <div class="p-4 bg-slate-900 text-white md:hidden flex justify-between items-center">
        <h1 class="font-bold text-lg">Anaconda Hub</h1>
        <span v-if="chatData.unsorted.length + chatData.groups.length > 0" 
              class="text-xs bg-red-600 px-2 rounded-full">
          {{ chatData.unsorted.length + chatData.groups.reduce((sum, g) => sum + g.contacts.length, 0) }}
        </span>
      </div>

      <!-- Unsorted Section -->
      <div class="flex-1 overflow-y-auto">
        <div v-if="loading" class="p-4 text-slate-500 text-sm">Загрузка...</div>
        <div v-else-if="error" class="p-4 text-red-600 text-sm">{{ error }}</div>

        <div v-if="chatData.unsorted.length" class="mb-2">
          <div class="px-4 py-2 text-xs font-bold text-slate-400 uppercase tracking-wider">Неразобранное</div>
          <div v-for="chat in chatData.unsorted" :key="chat.chat_id"
               @click="selectChat(chat)"
               class="p-3 border-b hover:bg-slate-50 cursor-pointer border-l-4 border-red-500 bg-red-50/30">
            <div class="font-bold text-red-700">{{ chat.display_name }}</div>
            <div class="text-xs text-slate-500 truncate">{{ chat.last_message }}</div>
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
                 @click="selectChat(chat)"
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
        Выберите диалог из списка
      </div>

      <!-- Chat Header -->
      <div v-else class="h-16 bg-white border-b shadow-sm flex items-center px-4 justify-between shrink-0">
        <div class="flex items-center gap-3">
          <button @click="backToHub" class="md:hidden w-8 h-8 flex items-center justify-center text-slate-600">
            <i class="fa-solid fa-arrow-left"></i>
          </button>

          <div>
            <div class="font-bold text-slate-800 leading-tight">{{ selectedChat.display_name }}</div>
            <div v-if="selectedChat.org_name" class="text-xs text-blue-600 font-semibold cursor-pointer hover:underline"
                 @click="openOrgModal(selectedChat)">
              {{ selectedChat.org_name }}
            </div>
            <div v-else class="text-xs text-red-500 font-bold">Неизвестный контакт</div>
          </div>
        </div>

        <!-- Action Button -->
        <div class="flex gap-2">
          <button v-if="!isContactKnown"
                  @click="openCreateContactModal"
                  class="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 transition font-semibold text-sm">
            + Привязать
          </button>
          <button class="w-10 h-10 bg-slate-100 rounded-full hover:bg-slate-200 text-slate-600">
            <i class="fa-solid fa-ellipsis-vertical"></i>
          </button>
        </div>
      </div>

      <!-- Messages Area -->
      <div v-if="selectedChat" class="flex-1 overflow-y-auto p-4 bg-[#e5ddd5]/30">
        <!-- Messages would be rendered here -->
        <div class="text-slate-500 text-center py-10">
          История сообщений (временно пусто)
        </div>
      </div>

      <!-- Message Input -->
      <div v-if="selectedChat" class="bg-white p-2 border-t flex items-center gap-2 shrink-0">
        <button class="p-3 text-slate-400 hover:text-slate-600">
          <i class="fa-solid fa-paperclip"></i>
        </button>
        <input class="flex-1 bg-slate-100 rounded-full py-2 px-4 focus:outline-none focus:ring-2 focus:ring-blue-500"
               placeholder="Сообщение..." />
        <button class="p-3 text-blue-600 hover:text-blue-700">
          <i class="fa-solid fa-paper-plane text-xl"></i>
        </button>
      </div>

    </div>

    <!-- CREATE CONTACT MODAL -->
    <div v-if="showCreateContactModal" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div class="bg-white rounded-lg p-6 max-w-md w-full mx-4 max-h-96 overflow-y-auto">
        <h3 class="text-xl font-bold mb-4">Привязать контакт</h3>

        <div class="space-y-4">
          <!-- Name (read-only) -->
          <div>
            <label class="block text-sm font-semibold mb-1">ФИО</label>
            <input v-model="newContactForm.name" type="text" disabled class="w-full border border-slate-300 rounded px-3 py-2 bg-slate-100">
          </div>

          <!-- Position -->
          <div>
            <label class="block text-sm font-semibold mb-1">Должность</label>
            <input v-model="newContactForm.position" type="text" class="w-full border border-slate-300 rounded px-3 py-2">
          </div>

          <!-- Organization Mode -->
          <div>
            <label class="block text-sm font-semibold mb-1">Организация *</label>
            <div class="space-y-2">
              <label class="flex items-center gap-2 cursor-pointer">
                <input v-model="newContactForm.org_mode" type="radio" value="existing" class="w-4 h-4">
                <span class="text-sm">Выбрать существующую</span>
              </label>
              <label class="flex items-center gap-2 cursor-pointer">
                <input v-model="newContactForm.org_mode" type="radio" value="new" class="w-4 h-4">
                <span class="text-sm">Создать новую</span>
              </label>
            </div>
          </div>

          <!-- Organization Selection / Creation -->
          <div v-if="newContactForm.org_mode === 'existing'" class="space-y-2">
            <select v-model="newContactForm.org_id" class="w-full border border-slate-300 rounded px-3 py-2 text-sm">
              <option :value="null">-- Выберите организацию --</option>
              <option v-for="group in chatData.groups" :key="group.org_id" :value="group.org_id">
                {{ group.org_name }}
              </option>
            </select>
          </div>

          <div v-if="newContactForm.org_mode === 'new'" class="space-y-2">
            <input v-model="newContactForm.new_org_name" type="text" placeholder="Название организации"
                   class="w-full border border-slate-300 rounded px-3 py-2 text-sm">
            <input v-model="newContactForm.inn" type="text" placeholder="ИНН (опционально)"
                   class="w-full border border-slate-300 rounded px-3 py-2 text-sm">
          </div>

          <!-- Buttons -->
          <div class="flex gap-3 pt-4">
            <button @click="showCreateContactModal = false"
                    class="flex-1 px-4 py-2 bg-slate-300 text-slate-900 rounded hover:bg-slate-400">
              Отмена
            </button>
            <button @click="createContact"
                    class="flex-1 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 font-semibold">
              Сохранить
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
            <p class="text-xs text-slate-500 uppercase">Организация ID</p>
            <p class="font-semibold">{{ selectedOrg.org_id }}</p>
          </div>
          <div>
            <p class="text-xs text-slate-500 uppercase">Контактов в системе</p>
            <p class="font-semibold">{{ selectedOrg.contacts.length }}</p>
          </div>
          <div>
            <p class="text-xs text-slate-500 uppercase">Непрочитанных сообщений</p>
            <p class="font-semibold">{{ selectedOrg.total_unread }}</p>
          </div>
        </div>

        <div class="border-t pt-4 mb-4">
          <p class="text-xs text-slate-500 uppercase mb-2">Контакты</p>
          <div class="space-y-2 max-h-40 overflow-y-auto">
            <div v-for="contact in selectedOrg.contacts" :key="contact.chat_id" class="text-sm">
              <p class="font-semibold">{{ contact.display_name }}</p>
              <p class="text-xs text-slate-600">{{ contact.position }}</p>
            </div>
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
/* Tailwind styles */
</style>
