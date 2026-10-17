<template>
  <div class="control-page">
    <div class="menubar">
      <h1>Lift Control</h1>
      <div class="power-indicator" :class="{ active: isAnyPowered }" title="Versorgungsspannung vorhanden" />
      <button class="e-stop" @click="emergencyStop">STOP</button>
    </div>
    <div v-if="statusText" class="control-status" role="status" aria-live="polite">
      <span>{{ statusText }}</span>
      <button v-if="stopped || resetPending" class="reset-button" :disabled="!connected || resetPending" @click="resetStop">
        {{ resetPending ? 'Freigabe läuft …' : 'STOP zurücksetzen / freigeben' }}
      </button>
    </div>
    <p v-if="brokerError" class="error-message" role="alert">
      {{ brokerError }} <button @click="brokerError = ''" aria-label="Fehlermeldung schließen">×</button>
    </p>
    <div class="lifts" ref="liftsContainer">
      <Lift
        v-for="entry in sortedLifts" :key="liftKey(entry.conId, entry.lift.id)"
        :con-id="entry.conId" :group="[entry.lift]" :enabled="canControl(entry.conId)"
        :controller-status="controllerLabel(entry.conId)"
        :active-indicators="activeIndicators" :pressed="pressed"
        @start="pressController.start" @end="pressController.end"
      />
      <p v-if="!Object.keys(onlineLifts).length" class="empty-state">Noch keine Controller verbunden.</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import Lift from '../components/Lift.vue'
import useWebSocket, {
  connected, connectionStatus, powerStates, onlineLifts, onlineControllers, controllers, stopped,
  resetPending, brokerError, controlEpoch, canControl,
} from '../services/websocket.js'
import { createPressController, liftKey } from '../services/pressController.js'

const liftsContainer = ref(null)
const pressed = ref(new Map())
const activeIndicators = ref(new Set())
const { send, emergencyStop, resetStop, onMessage, startup } = useWebSocket()
const pressController = createPressController({
  send,
  canStart: conId => canControl(conId) && document.visibilityState !== 'hidden' && document.hasFocus(),
  getEpoch: () => controlEpoch.value,
  onChange: state => {
    pressed.value = state.pressed
    activeIndicators.value = state.indicators
  },
})

const sortedLifts = computed(() => Object.entries(onlineLifts.value)
  .flatMap(([conId, group]) => Object.values(group).map(lift => ({ conId, lift })))
  .sort((a, b) => a.lift.id - b.lift.id || a.conId.localeCompare(b.conId, undefined, { numeric: true })))

const isAnyPowered = computed(() => Object.values(powerStates.value).some(value => value === 1))
const statusText = computed(() => {
  if (!connected.value) return connectionStatus.value === 'connecting' ? 'Verbindung wird hergestellt …' : 'Keine Verbindung zum Server'
  if (resetPending.value) return 'Controller werden freigegeben. Alle Tasten loslassen.'
  if (stopped.value) return 'STOP aktiv. Zum Betrieb bewusst freigeben.'
  return ''
})

function controllerLabel(conId) {
  if (!connected.value || !onlineControllers.value.has(conId) || !controllers.value[conId]) return 'Controller nicht verbunden'
  if (controllers.value[conId].ready && !controllers.value[conId].stopped) return 'Bereit'
  return 'Controller gesperrt'
}

const removeListener = onMessage(data => {
  if (data.case === 'lift_moved') pressController.acknowledge(data)
  if (data.case === 'error') pressController.reject(data.command_id)
})

watch([connected, stopped, resetPending, controllers, onlineControllers], () => {
  pressController.cancelWhere(conId => !canControl(conId))
}, { flush: 'sync' })
watch(controlEpoch, () => pressController.cancelWhere(), { flush: 'sync' })

const cancelPresses = () => pressController.cancelWhere()
const visibilityChanged = () => {
  if (document.visibilityState === 'hidden') cancelPresses()
}
let wheelTargetIndex = null
let lastWheelStep = -Infinity
watch(() => sortedLifts.value.map(({ conId, lift }) => liftKey(conId, lift.id)).join('|'), () => {
  // A controller joining can move cards: require a new press on the new layout.
  cancelPresses()
  wheelTargetIndex = null
  lastWheelStep = -Infinity
}, { flush: 'sync' })

function scrollLifts(event) {
  const container = liftsContainer.value
  // Leave zoom and native horizontal trackpad scrolling to the browser.
  if (event.ctrlKey || Math.abs(event.deltaY) <= Math.abs(event.deltaX)) return
  const count = container.querySelectorAll(':scope > .lift').length
  if (count < 2 || container.clientWidth === 0) return
  event.preventDefault()

  const now = performance.now()
  if (now - lastWheelStep < 300) return
  // Keep the requested page while a smooth scroll is in progress. Otherwise
  // short wheel steps can snap back or repeatedly target the current card.
  const current = wheelTargetIndex !== null && now - lastWheelStep < 700
    ? wheelTargetIndex
    : Math.round(container.scrollLeft / container.clientWidth)
  wheelTargetIndex = Math.max(0, Math.min(count - 1, current + Math.sign(event.deltaY)))
  lastWheelStep = now
  cancelPresses()
  container.scrollTo({
    left: wheelTargetIndex * container.clientWidth,
    behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth',
  })
}

onMounted(() => {
  window.addEventListener('blur', cancelPresses)
  window.addEventListener('pagehide', cancelPresses)
  document.addEventListener('visibilitychange', visibilityChanged)
  liftsContainer.value.addEventListener('wheel', scrollLifts, { passive: false })
  startup()
})

onBeforeUnmount(() => {
  cancelPresses()
  removeListener()
  window.removeEventListener('blur', cancelPresses)
  window.removeEventListener('pagehide', cancelPresses)
  document.removeEventListener('visibilitychange', visibilityChanged)
  liftsContainer.value?.removeEventListener('wheel', scrollLifts)
})
</script>
