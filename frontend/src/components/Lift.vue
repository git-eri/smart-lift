<template>
  <div
    v-for="lift in group"
    :key="lift.id"
    class="lift"
  >
    <div class="lift-header">
      <div v-if="editingLiftId !== lift.id">
        <h1>
          {{ lift.name }}
          <button @click="startEditing(lift)" class="edit-btn">✏️</button>
        </h1>
      </div>
      <div v-else>
        <input
          v-model="newName"
          @keyup.enter="submitRename(lift)"
          @blur="submitRename(lift)"
          class="rename-input"
        />
      </div>
    </div>

    <div
      class="buttons"
      v-for="(label, dir) in ['Up', 'Down', 'Lock']"
      :key="dir"
    >
      <button
        class="button"
        @pointerdown="() => emit('start', conId, lift.id, dir)"
        @pointerup="() => emit('end', conId, lift.id, dir)"
        @pointerleave="() => emit('end', conId, lift.id, dir)"
      >
        {{ label }}
      </button>
      <div :id="`indicator${lift.id}-${dir}`" class="indicator"></div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  conId: String,
  group: Object
})
const emit = defineEmits(['start', 'end'])

const editingLiftId = ref(null)
const newName = ref('')

const PROTOCOL = import.meta.env.VITE_USE_SSL === 'true' ? 'https' : 'http'
const PORT = import.meta.env.VITE_BACKEND_PORT || '8000'

function startEditing(lift) {
  editingLiftId.value = lift.id
  newName.value = lift.name
}

async function submitRename(lift) {
  if (newName.value.trim() === '' || newName.value === lift.name) {
    editingLiftId.value = null
    return
  }

  try {
    const response = await fetch(`${PROTOCOL}://${location.hostname}:${PORT}/admin/lift-rename`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        lift_id: lift.id.toString(),
        new_name: newName.value.trim()
      })
    })

    if (!response.ok) {
      throw new Error('Server error')
    }

    lift.name = newName.value
  } catch (err) {
    console.error('Failed to rename lift:', err)
    alert('Lift konnte nicht umbenannt werden.')
  } finally {
    editingLiftId.value = null
  }
}
</script>

<style scoped>
.lift-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.edit-btn {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 1rem;
}
.rename-input {
  font-size: 1.2rem;
  padding: 6px 10px;
  border: 1px solid #bbb;
  border-radius: 6px;
  outline: none;
  width: 100%;
  max-width: 300px;
  box-sizing: border-box;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.rename-input:focus {
  border-color: #007bff;
  box-shadow: 0 0 4px rgba(0, 123, 255, 0.4);
}
</style>
