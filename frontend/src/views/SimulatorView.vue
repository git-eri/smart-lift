<template>
  <div class="control-page">
    <div class="menubar"><h2>Controller-Simulator</h2><RouterLink to="/">Zur Steuerung</RouterLink></div>
    <div class="control-status">
      <span>{{ status }} · {{ conId }}</span>
      <button @click="startup" :disabled="socketActive">Verbinden</button>
      <button @click="shutdown" :disabled="!socketActive">Trennen</button>
    </div>
    <p class="control-status">Simulierte Relais · {{ modelState.stopped ? 'STOP aktiv' : 'Freigegeben' }}</p>
    <p v-if="error" class="error-message" role="alert">{{ error }}</p>
    <div class="lifts">
      <div v-for="lift in lifts" :key="lift" class="lift">
        <h1>Lift {{ lift }}</h1>
        <div v-for="(label, dir) in ['Hoch', 'Runter', 'Entriegeln']" :key="dir" class="buttons">
          <span class="button">{{ label }}</span>
          <div class="indicator" :class="{ active: modelState.active.get(lift)?.direction === dir }" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onBeforeUnmount } from 'vue'
import { randomId, websocketUrl } from '../services/urls.js'
import { createControllerSimulator } from '../services/controllerSimulator.js'

const conId = randomId('con-sim')
// Optional URL hash #0-4 selects up to five simulated lift IDs.
const range = window.location.hash.match(/^#(\d+)-(\d+)$/)
const start = range ? Number(range[1]) : 0
const end = range ? Number(range[2]) : 4
const validRange = Number.isSafeInteger(start) && Number.isSafeInteger(end) && start >= 0 && end <= 1_000_000 && end >= start && end - start < 5
const lifts = validRange ? Array.from({ length: end - start + 1 }, (_, index) => start + index) : [0, 1, 2, 3, 4]
const status = ref('Nicht verbunden')
const socketActive = ref(false)
const error = ref('')
const modelState = ref({ ready: false, stopped: true, active: new Map() })
let ws = null
let timer = null
const model = createControllerSimulator({
  lifts, conId,
  send: data => {
    if (ws?.readyState !== WebSocket.OPEN) return false
    try { ws.send(JSON.stringify(data)); return true } catch { shutdown(); return false }
  },
  onChange: state => { modelState.value = state },
})

function startup() {
  if (socketActive.value) return
  error.value = ''
  status.value = 'Verbindung wird hergestellt …'
  const socket = new WebSocket(websocketUrl(conId))
  ws = socket
  socketActive.value = true
  socket.onopen = () => {
    if (ws !== socket) return
    status.value = 'Verbunden'
    model.hello()
    timer = setInterval(model.tick, 50)
  }
  socket.onmessage = event => {
    if (ws !== socket) return
    try {
      const data = JSON.parse(event.data)
      if (data.case === 'error') error.value = typeof data.detail === 'string' ? data.detail : 'Server hat Anfrage abgelehnt.'
      else model.receive(data)
    } catch {
      error.value = 'Ungültige Nachricht vom Server.'
      shutdown()
    }
  }
  socket.onclose = () => { if (ws === socket) shutdown() }
  socket.onerror = () => {
    if (ws !== socket) return
    error.value = 'Simulator konnte keine Verbindung herstellen.'
    shutdown()
  }
}

function shutdown() {
  const socket = ws
  ws = null
  if (timer !== null) clearInterval(timer)
  timer = null
  model.disconnect()
  socket?.close()
  socketActive.value = false
  status.value = 'Nicht verbunden'
}

window.addEventListener('pagehide', shutdown)
document.addEventListener('visibilitychange', visibilityChanged)
function visibilityChanged() {
  if (document.visibilityState === 'hidden') shutdown()
}
onBeforeUnmount(() => {
  shutdown()
  window.removeEventListener('pagehide', shutdown)
  document.removeEventListener('visibilitychange', visibilityChanged)
})
</script>
