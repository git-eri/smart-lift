<template>
  <div>
    <div class="menubar"><h1>Admin Panel</h1><RouterLink to="/">Zur Steuerung</RouterLink></div>
    <main class="admin-panel">
      <p role="status">{{ connected ? 'Mit Server verbunden' : 'Keine Verbindung zum Server' }}</p>
      <h2>Lift umbenennen</h2>
      <form @submit.prevent="submitRename" v-if="selectedLift">
        <label for="lift-id">Lift-ID:</label><input id="lift-id" :value="selectedLift.id" disabled />
        <label for="newName">Neuer Name:</label><input id="newName" v-model="newName" required maxlength="80" />
        <button class="button" type="submit" :disabled="saving || !connected">Name ändern</button>
      </form>
      <p v-if="message" role="status">{{ message }}</p>
      <h2>Bekannte Lifte</h2>
      <ul v-if="Object.keys(onlineLifts).length">
        <li v-for="(group, conId) in onlineLifts" :key="conId">
          <strong>{{ conId }}</strong>
          <ul><li v-for="lift in group" :key="lift.id">
            {{ lift.name }} (ID: {{ lift.id }})
            <button @click="selectLift(lift)">Umbenennen</button>
          </li></ul>
        </li>
      </ul>
      <p v-else>Keine Lifte bekannt.</p>
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import useWebSocket, { connected, onlineLifts } from '../services/websocket.js'
import { apiPath } from '../services/urls.js'

const selectedLift = ref(null)
const newName = ref('')
const message = ref('')
const saving = ref(false)
const { startup } = useWebSocket()
onMounted(startup)

function selectLift(lift) {
  selectedLift.value = lift
  newName.value = lift.name
  message.value = ''
}

async function submitRename() {
  if (saving.value || !selectedLift.value || !newName.value.trim()) return
  saving.value = true
  try {
    const response = await fetch(apiPath('admin/lift-rename'), {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ lift_id: selectedLift.value.id, new_name: newName.value.trim() }),
    })
    if (!response.ok) throw new Error()
    message.value = 'Liftname geändert.'
  } catch {
    message.value = 'Lift konnte nicht umbenannt werden.'
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.admin-panel { padding: 2rem; overflow: auto; height: 90vh; }
form { display: flex; flex-direction: column; max-width: 300px; gap: 0.5rem; margin-bottom: 2rem; }
input { padding: 0.5rem; border: 1px solid #ccc; border-radius: 5px; }
</style>
