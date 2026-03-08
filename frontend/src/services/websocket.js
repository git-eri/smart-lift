import { ref } from 'vue'

const ws = ref(null)
const listeners = new Set()

const clientId = 'cli-' + Date.now()

let reconnectTimer = null
let reconnectDelay = 1000
const maxReconnectDelay = 10000

export const powerStates = ref({})

const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
const url = `${protocol}://${window.location.host}/api/ws/${clientId}`

function connect() {
  if (
    ws.value &&
    (ws.value.readyState === WebSocket.OPEN ||
     ws.value.readyState === WebSocket.CONNECTING)
  ) {
    return
  }

  console.log('[WS] Connecting...')

  const socket = new WebSocket(url)
  ws.value = socket

  socket.onopen = () => {
    console.log('[WS] Connected', socket)

    reconnectDelay = 1000
    clearTimeout(reconnectTimer)
  }

  socket.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)

      if (data.case === 'power_states') {
        powerStates.value = { ...data.states }
      }

      else if (data.case === 'power_state' && data.con_id) {
        powerStates.value = {
          ...powerStates.value,
          [data.con_id]: Number(data.state) ? 1 : 0
        }
      }

      listeners.forEach(cb => cb(data))

    } catch (err) {
      console.error('[WS] Invalid JSON:', event.data)
    }
  }

  socket.onclose = () => {
    console.warn('[WS] Closed')
    scheduleReconnect()
  }

  socket.onerror = () => {
    console.warn('[WS] Error')
  }
}

function scheduleReconnect() {
  if (reconnectTimer) return

  reconnectTimer = setTimeout(() => {
    reconnectTimer = null

    reconnectDelay = Math.min(reconnectDelay * 2, maxReconnectDelay)

    console.log(`[WS] Reconnecting in ${reconnectDelay}ms`)
    connect()

  }, reconnectDelay)
}

function startup() {
  connect()
}

function send(payload) {
  if (ws.value?.readyState === WebSocket.OPEN) {
    ws.value.send(JSON.stringify({
      ...payload,
      client_id: clientId
    }))
  } else {
    console.warn('[WS] Send failed — socket not open')
  }
}

function emergencyStop() {
  send({ case: 'stop' })
}

function onMessage(cb) {
  listeners.add(cb)

  return () => {
    listeners.delete(cb)
  }
}

document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible') {
    startup()
  }
})

window.addEventListener('focus', startup)

export default () => ({
  send,
  emergencyStop,
  onMessage,
  startup
})