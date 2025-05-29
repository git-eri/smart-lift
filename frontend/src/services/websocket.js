import { ref } from 'vue'

const ws = ref(null)
const clientId = 'cli-' + Date.now()
let listeners = []

// Lade Umgebungsvariablen aus Vite
const VITE_BACKEND_PORT = import.meta.env.VITE_BACKEND_PORT || 8000
const WS_PROTOCOL = import.meta.env.VITE_USE_SSL === true ? 'wss' : 'ws'

function startup() {
  if (ws.value && ws.value.readyState !== WebSocket.CLOSED) return

  const url = `${WS_PROTOCOL}://${location.hostname}:${VITE_BACKEND_PORT}/ws/${clientId}`
  ws.value = new WebSocket(url)

  ws.value.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      listeners.forEach((cb) => cb(data))
    } catch (e) {
      console.error('Invalid JSON:', event.data)
    }
  }
}

function send(payload) {
  if (ws.value?.readyState === WebSocket.OPEN) {
    ws.value.send(JSON.stringify({ ...payload, client_id: clientId }))
  }
}

function emergencyStop() {
  send({ case: 'stop' })
}

function onMessage(cb) {
  listeners.push(cb)
}

export default () => ({ send, emergencyStop, onMessage, startup })
