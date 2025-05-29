<template>
  <div>
    <div class="menubar">
      <h2>Controller Simulator</h2>
    </div>
    <div style="padding: 1rem;">
      <button class="button" @click="startup">Startup</button>
      <button class="button" @click="shutdown">Shutdown</button>
    </div>
    <div class="lifts">
      <div v-for="lift in lifts" :key="lift" class="lift">
        <h1>Lift {{ lift }}</h1>
        <div v-for="dir in 3" :key="dir" class="buttons">
          <button class="button">{{ ['Up', 'Down', 'Lock'][dir - 1] }}</button>
          <div :id="`indicator${lift}-${dir - 1}`" class="indicator"></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const lifts = ref([])
const client_id = Date.now()
let ws

function startup() {
  const ids = (document.location.hash || '#1-3').substring(1).split('-')
  for (let i = parseInt(ids[0]); i <= parseInt(ids[1]); i++) {
    lifts.value.push(i)
  }

  ws = new WebSocket(`wss://${location.hostname}:8000/ws/con-sim${client_id}`)
  const hello = { case: 'hello', lifts: lifts.value }

  ws.onopen = () => ws.send(JSON.stringify(hello))

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data)
    if (data.case === 'move_lift') {
      const indicator = document.getElementById(`indicator${data.lift_id}-${data.direction}`)
      if (indicator) {
        if (data.toggle === 1) indicator.classList.add('active')
        else indicator.classList.remove('active')
      }
      ws.send(JSON.stringify({
        case: 'lift_moved',
        lift_id: data.lift_id,
        direction: data.direction,
        toggle: data.toggle
      }))
    }
  }
}

function shutdown() {
  lifts.value = []
  ws?.close()
}
</script>