import { computed, ref } from 'vue'
import { randomId, websocketUrl } from './urls.js'
import { createSocketTransport } from './socketTransport.js'

const listeners = new Set()
const clientId = randomId('cli')
export const connectionStatus = ref('disconnected')
export const connected = computed(() => connectionStatus.value === 'connected')
export const powerStates = ref({})
export const onlineLifts = ref({})
export const onlineControllers = ref(new Set())
export const controllers = ref({})
export const stopped = ref(true)
export const resetPending = ref(false)
export const controlEpoch = ref(null)
export const brokerError = ref('')

const transport = createSocketTransport({
  url: websocketUrl(clientId),
  onStatus(status) {
    connectionStatus.value = status
    if (status !== 'connected') {
      stopped.value = true
      resetPending.value = false
      controlEpoch.value = null
      powerStates.value = {}
      controllers.value = {}
      onlineControllers.value = new Set()
    }
  },
  onMessage(data) {
    switch (data.case) {
      case 'online_lifts':
        // Keep known cards visible during controller outages.
        onlineControllers.value = new Set(Object.keys(data.lifts || {}))
        onlineLifts.value = { ...onlineLifts.value, ...data.lifts }
        break
      case 'power_states':
        powerStates.value = { ...data.states }
        break
      case 'power_state':
        if (data.con_id) powerStates.value = { ...powerStates.value, [data.con_id]: data.state === 1 ? 1 : 0 }
        break
      case 'control_state':
        controlEpoch.value = typeof data.control_epoch === 'string' ? data.control_epoch : null
        controllers.value = { ...data.controllers }
        stopped.value = data.stopped !== false
        resetPending.value = data.reset_pending === true
        break
      case 'stop':
        stopped.value = true
        resetPending.value = false
        break
      case 'error':
        brokerError.value = typeof data.detail === 'string' ? data.detail : 'Der Server hat die Anfrage abgelehnt.'
        resetPending.value = false
        break
    }
    for (const listener of listeners) listener(data)
  },
})

export function canControl(conId) {
  return connected.value && !!controlEpoch.value && !stopped.value && !resetPending.value &&
    onlineControllers.value.has(conId) && controllers.value[conId]?.ready === true &&
    controllers.value[conId]?.stopped === false
}

function send(payload) {
  return transport.send({ ...payload, client_id: clientId })
}

function emergencyStop() {
  stopped.value = true
  resetPending.value = false
  if (!send({ case: 'stop' })) brokerError.value = 'Keine Verbindung. STOP konnte nicht übertragen werden.'
}

function resetStop() {
  if (!connected.value || !stopped.value || resetPending.value) return
  brokerError.value = ''
  resetPending.value = true
  if (!send({ case: 'reset_stop' })) {
    resetPending.value = false
    brokerError.value = 'Keine Verbindung. Die Freigabe konnte nicht übertragen werden.'
  }
}

function onMessage(callback) {
  listeners.add(callback)
  return () => listeners.delete(callback)
}

window.addEventListener('focus', transport.startup)
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible') transport.startup()
})

export default () => ({ send, emergencyStop, resetStop, onMessage, startup: transport.startup })
