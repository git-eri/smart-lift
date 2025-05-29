import { ref } from 'vue'

const ws = ref(null)
const clientId = 'cli-' + Date.now()
let listeners = []

function startup() {
  if (ws.value && ws.value.readyState !== WebSocket.CLOSED) return

  const url = `wss://${location.hostname}:8000/ws/${clientId}`
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
