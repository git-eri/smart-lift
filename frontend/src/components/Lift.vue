<template>
  <div v-for="lift in group" :key="lift.id" class="lift" :class="{ unavailable: !enabled }">
    <div class="lift-header">
      <h1 v-if="editingLiftId !== lift.id">
        {{ lift.name }}
        <button @click="startEditing(lift)" class="edit-btn" :aria-label="`${lift.name} umbenennen`">✎</button>
      </h1>
      <input v-else v-model="newName" @keyup.enter="submitRename(lift)" @keyup.esc="editingLiftId = null"
        @blur="submitRename(lift)" class="rename-input" maxlength="80" aria-label="Neuer Liftname" />
    </div>
    <p class="controller-status">{{ controllerStatus }} · {{ conId }}</p>
    <p v-if="renameError" class="error-message" role="alert">{{ renameError }}</p>
    <div class="buttons" v-for="(label, dir) in ['Hoch', 'Runter', 'Entriegeln']" :key="dir">
      <button
        class="button motion-button" :disabled="!enabled || otherDirectionPressed(lift.id, dir)"
        :class="{ pressed: isPressed(lift.id, dir) }" :aria-pressed="isPressed(lift.id, dir)"
        @pointerdown="startPointer($event, lift.id, dir)"
        @pointerup="endPointer($event, lift.id, dir)"
        @pointercancel="endPointer($event, lift.id, dir)"
        @lostpointercapture="endPointer($event, lift.id, dir)"
        @keydown="startKey($event, lift.id, dir)" @keyup="endKey($event, lift.id, dir)"
        @blur="endOwned(lift.id, dir)" @contextmenu.prevent @dragstart.prevent
      >{{ label }}</button>
      <div class="indicator" :class="{ active: activeIndicators.has(indicatorKey(conId, lift.id, dir)) }"
        :aria-label="`${label}: ${activeIndicators.has(indicatorKey(conId, lift.id, dir)) ? 'aktiv' : 'aus'}`" />
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onBeforeUnmount } from 'vue'
import { apiPath } from '../services/urls.js'
import { liftKey, indicatorKey } from '../services/pressController.js'

const props = defineProps({
  conId: { type: String, required: true },
  group: { type: [Array, Object], required: true },
  enabled: Boolean,
  controllerStatus: String,
  activeIndicators: { type: Set, required: true },
  pressed: { type: Map, required: true },
})
const emit = defineEmits(['start', 'end'])
const owners = new Map()
const editingLiftId = ref(null)
const newName = ref('')
const renameError = ref('')
let renaming = false

const isPressed = (id, dir) => props.pressed.get(liftKey(props.conId, id))?.direction === dir
const otherDirectionPressed = (id, dir) => props.pressed.has(liftKey(props.conId, id)) && !isPressed(id, dir)

function startPointer(event, id, dir) {
  if (event.button !== 0 || !props.enabled || props.pressed.has(liftKey(props.conId, id)) || owners.has(id)) return
  event.preventDefault()
  event.currentTarget.focus({ preventScroll: true })
  owners.set(id, { kind: 'pointer', pointerId: event.pointerId, dir, element: event.currentTarget })
  event.currentTarget.setPointerCapture(event.pointerId)
  emit('start', props.conId, id, dir)
}

function endPointer(event, id, dir) {
  const owner = owners.get(id)
  if (owner?.kind === 'pointer' && owner.pointerId === event.pointerId && owner.dir === dir) endOwned(id, dir)
}

function startKey(event, id, dir) {
  if (![' ', 'Enter'].includes(event.key)) return
  event.preventDefault()
  if (event.repeat || !props.enabled || props.pressed.has(liftKey(props.conId, id)) || owners.has(id)) return
  owners.set(id, { kind: 'key', key: event.key, dir })
  emit('start', props.conId, id, dir)
}

function endKey(event, id, dir) {
  if (![' ', 'Enter'].includes(event.key)) return
  event.preventDefault()
  const owner = owners.get(id)
  if (owner?.kind === 'key' && owner.key === event.key && owner.dir === dir) endOwned(id, dir)
}

function clearOwner(id) {
  const owner = owners.get(id)
  owners.delete(id)
  if (owner?.kind === 'pointer' && owner.element.hasPointerCapture(owner.pointerId)) owner.element.releasePointerCapture(owner.pointerId)
}

function endOwned(id, dir) {
  if (owners.get(id)?.dir !== dir) return
  clearOwner(id)
  emit('end', props.conId, id, dir)
}

watch(() => props.pressed, () => {
  for (const [id, owner] of owners) if (!isPressed(id, owner.dir)) clearOwner(id)
}, { flush: 'post' })
onBeforeUnmount(() => {
  for (const [id, owner] of owners) endOwned(id, owner.dir)
})

function startEditing(lift) {
  editingLiftId.value = lift.id
  newName.value = lift.name
  renameError.value = ''
}

async function submitRename(lift) {
  if (renaming || editingLiftId.value !== lift.id) return
  const name = newName.value.trim()
  editingLiftId.value = null
  if (!name || name === lift.name) return
  renaming = true
  try {
    const response = await fetch(apiPath('admin/lift-rename'), {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ lift_id: lift.id, new_name: name }),
    })
    if (!response.ok) throw new Error()
    // The server broadcasts the authoritative name to all clients.
  } catch {
    renameError.value = 'Lift konnte nicht umbenannt werden.'
  } finally {
    renaming = false
  }
}
</script>

<style scoped>
.lift-header { display: flex; align-items: center; gap: 0.5rem; }
.edit-btn { background: none; border: none; cursor: pointer; font-size: 1rem; color: inherit; }
.rename-input { font-size: 1.2rem; padding: 6px 10px; border: 1px solid #bbb; border-radius: 6px; width: 100%; max-width: 300px; }
</style>
