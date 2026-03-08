<template>
  <div>
    <div class="menubar">
      <h1>Lift Control</h1>
      <div
        class="power-indicator"
        :class="{ active: isAnyPowered }"
        title="Controller power status"
      ></div>
      <button class="e-stop" @click="emergencyStop">STOP</button>
    </div>
    <div class="lifts">
      <Lift
        v-for="(group, conId) in lifts"
        :key="conId"
        :con-id="conId"
        :group="group"
        :active-indicators="activeIndicators"
        @start="startLift"
        @end="endLift"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import Lift from '../components/Lift.vue'
import useWebSocket from '../services/websocket.js'
import { powerStates } from '../services/websocket.js'

const lifts = ref({})
const activeLifts = ref(new Set())
const activeIndicators = ref(new Set())
const { send, emergencyStop, onMessage, startup } = useWebSocket()

const isAnyPowered = computed(() => {
  return Object.values(powerStates.value).some(v => v === 1)
})

let removeListener

onMounted(() => {
  startup()

  removeListener = onMessage((data) => {
    switch (data.case) {
      case 'online_lifts':
        lifts.value = data.lifts
        break

      case 'stop':
        alert('EMERGENCY STOP')
        break

      case 'lift_moved':
        const key = `${data.lift_id}-${data.direction}`

        const next = new Set(activeIndicators.value)

        if (data.toggle === 1) {
          next.add(key)
        } else {
          next.delete(key)
        }

        activeIndicators.value = next
        break
    }
  })
})

onUnmounted(() => {
  removeListener?.()
})

function startLift(conId, liftId, dir) {
  const key = `${liftId}-${dir}`
  if (!activeLifts.value.has(key)) {
    activeLifts.value.add(key)
    send({ case: 'move_lift', con_id: conId, lift_id: liftId, direction: dir, toggle: 1 })
  }
}

function endLift(conId, liftId, dir) {
  const key = `${liftId}-${dir}`
  if (activeLifts.value.has(key)) {
    activeLifts.value.delete(key)
    send({ case: 'move_lift', con_id: conId, lift_id: liftId, direction: dir, toggle: 0 })
  }
}
</script>
