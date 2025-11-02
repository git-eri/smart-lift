import { ref } from 'vue'

const ws = ref(null)
const clientId = 'cli-' + Date.now()
let listeners = []
let reconnectTimer = null
let reconnectDelay = 1000 // ms

export const powerStates = ref({})

const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
const host = window.location.hostname
const port = window.location.port ? `:${window.location.port}` : ''
const url = `${protocol}://${host}${port}/api/ws/${clientId}`

function connect() {
  ws.value = new WebSocket(url)

  ws.value.onopen = () => {
    console.log('[WS] Connected')
    clearTimeout(reconnectTimer)
  }

  ws.value.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)

      if (data.case === 'power_states') {
        powerStates.value = { ...data.states }
      } 
      else if (data.case === 'power_state' && data.con_id) {
        powerStates.value = { ...powerStates.value, [data.con_id]: Number(data.state) ? 1 : 0 }
      }

      listeners.forEach((cb) => cb(data))
    } catch (e) {
      console.error('[WS] Invalid JSON:', event.data)
    }
  }

  ws.value.onclose = () => {
    console.warn('[WS] Closed — retrying...')
    scheduleReconnect()
  }

  ws.value.onerror = () => {
    console.warn('[WS] Error — retrying...')
    ws.value?.close()
    scheduleReconnect()
  }
}

function scheduleReconnect() {
  clearTimeout(reconnectTimer)
  reconnectTimer = setTimeout(() => {
    console.log('[WS] Reconnecting...')
    connect()
  }, reconnectDelay)
}

function startup() {
  if (!ws.value || ws.value.readyState === WebSocket.CLOSED) {
    connect()
  }
}

// reconnect when tab becomes visible again
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible') {
    console.log('[WS] Tab visible — ensure connection')
    if (!ws.value || ws.value.readyState !== WebSocket.OPEN) {
      startup()
    }
  }
})

function send(payload) {
  if (ws.value?.readyState === WebSocket.OPEN) {
    ws.value.send(JSON.stringify({ ...payload, client_id: clientId }))
  } else {
    console.warn('[WS] Send failed — socket not open')
  }
}

function emergencyStop() {
  send({ case: 'stop' })
}

function onMessage(cb) {
  listeners.push(cb)
}

export default () => ({ send, emergencyStop, onMessage, startup })
