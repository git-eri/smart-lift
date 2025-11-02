import { ref } from 'vue'

const ws = ref(null)
const clientId = 'cli-' + Date.now()
let listeners = []

const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
const host = window.location.hostname
const port = window.location.port ? `:${window.location.port}` : ''
const url = `${protocol}://${host}${port}/api/ws/${clientId}`

export const powerStates = ref({})

function startup() {
  if (ws.value && ws.value.readyState !== WebSocket.CLOSED) return

  ws.value = new WebSocket(url)

  ws.value.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      if (data.case === 'power_states' && data.states && typeof data.states === 'object') {
        powerStates.value = { ...data.states }
      } else if (data.case === 'power_state' && data.con_id) {
        powerStates.value = { ...powerStates.value, [data.con_id]: Number(data.state) ? 1 : 0 }
      }
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
