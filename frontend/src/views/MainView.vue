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
    <div class="lifts" ref="liftsContainer">
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
const liftsContainer = ref(null)
const activeLifts = ref(new Set())
const activeIndicators = ref(new Set())
const { send, emergencyStop, onMessage, startup } = useWebSocket()

const isAnyPowered = computed(() => {
  return Object.values(powerStates.value).some(v => v === 1)
})

let removeListener

onMounted(() => {
  startup()
  const el = liftsContainer.value

  let isDown = false
  let startX
  let scrollLeft

  removeListener = onMessage((data) => {
    switch (data.case) {
      case 'online_lifts':
        console.log(data.lifts)
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

    el.addEventListener('mousedown', (e) => {
    isDown = true
    el.classList.add('dragging')
    startX = e.pageX - el.offsetLeft
    scrollLeft = el.scrollLeft
  })

  el.addEventListener('mouseleave', () => {
    isDown = false
    el.classList.remove('dragging')
  })

  el.addEventListener('mouseup', () => {
    isDown = false
    el.classList.remove('dragging')
  })

  el.addEventListener('mousemove', (e) => {
    if (!isDown) return
    e.preventDefault()
    const x = e.pageX - el.offsetLeft
    const walk = (x - startX) * 1.5
    el.scrollLeft = scrollLeft - walk
  })

  el.addEventListener('wheel', (e) => {
    if (Math.abs(e.deltaY) > Math.abs(e.deltaX)) {
      el.scrollLeft += e.deltaY
      e.preventDefault()
    }
  }, { passive: false })
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
