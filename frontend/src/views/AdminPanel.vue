<template>
  <div>
    <div class="menubar">
      <h1>Admin Panel</h1>
    </div>
    <div style="padding: 2rem;">
      <h2>Lift umbenennen</h2>
      <form @submit.prevent="submitRename" v-if="selectedLift">
        <label for="lift">Lift-ID:</label>
        <input type="text" v-model="selectedLift.id" disabled />

        <label for="newName">Neuer Name:</label>
        <input type="text" id="newName" v-model="newName" required />

        <button class="button" type="submit">Name ändern</button>
      </form>

      <h2 style="margin-top: 2rem;">Verbundene Lifte</h2>
      <ul v-if="Object.keys(lifts).length">
        <li v-for="(group, conId) in lifts" :key="conId">
          <strong>{{ conId }}</strong>:
          <ul>
            <li v-for="lift in group" :key="lift.id">
              {{ lift.name }} (ID: {{ lift.id }})
              <button class="button" @click="selectLift(lift)">Umbenennen</button>
            </li>
          </ul>
        </li>
      </ul>
      <p v-else>Keine Lifte verbunden.</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import useWebSocket from '../services/websocket.js'

const lifts = ref({})
const selectedLift = ref(null)
const newName = ref('')

const { send, onMessage, startup } = useWebSocket()

onMounted(() => {
  startup()
  onMessage(data => {
    if (data.case === 'online_lifts') {
      lifts.value = data.lifts
    }
  })
})

function selectLift(lift) {
  selectedLift.value = lift
  newName.value = lift.name
}

async function submitRename() {
  const response = await fetch(`https://${location.hostname}:8000/admin/lift-rename`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ lift_id: selectedLift.value.id.toString(), new_name: newName.value })
  })
  console.log(JSON.stringify({ lift_id: selectedLift.value.id.toString(), new_name: newName.value }));

  if (response.ok) {
    alert('Liftname geändert!')
    selectedLift.value.name = newName.value
  } else {
    alert('Fehler beim Umbenennen')
  }
}
</script>

<style scoped>
form {
  display: flex;
  flex-direction: column;
  max-width: 300px;
  gap: 0.5rem;
  margin-bottom: 2rem;
}

input[type="text"] {
  padding: 0.5rem;
  border: 1px solid #ccc;
  border-radius: 5px;
}
</style>