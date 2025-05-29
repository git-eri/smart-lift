<template>
  <div>
    <div class="menubar">
      <h1>Lift Control</h1>
      <button class="e-stop" @click="emergencyStop">STOP</button>
    </div>
    <div class="lifts">
      <Lift
        v-for="(group, conId) in lifts"
        :key="conId"
        :con-id="conId"
        :group="group"
        @start="startLift"
        @end="endLift"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import Lift from '../components/Lift.vue'
import useWebSocket from '../services/websocket.js'

const lifts = ref({})
const activeLifts = ref(new Set())
const { send, emergencyStop, onMessage, startup } = useWebSocket()

onMounted(() => {
  startup()
  onMessage((data) => {
    switch (data.case) {
      case 'online_lifts':
        lifts.value = data.lifts
        break
      case 'stop':
        alert('EMERGENCY STOP')
        break
      case 'lift_moved':
        const { lift_id, direction, toggle } = data
        const indicator = document.getElementById(`indicator${lift_id}-${direction}`)
        if (indicator) {
          if (toggle === 1) indicator.classList.add('active')
          else indicator.classList.remove('active')
        }
        break
    }
  })
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
