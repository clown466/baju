<script>
export default { name: 'ArtifactTab' }
</script>
<script setup>
import { onMounted, ref } from 'vue'
import * as api from '../api'
import EditorPane from '../components/EditorPane.vue'

const props = defineProps({
  pid: { type: String, required: true },
  kind: { type: String, required: true },
  generateLabel: { type: String, required: true },
})

const generators = { analysis: api.stage2Generate, outline: api.stage4Generate }

const content = ref('')
const busy = ref(false)
const error = ref('')

async function load() {
  try {
    content.value = (await api.getArtifact(props.pid, props.kind)).content
  } catch {
    content.value = ''
  }
}

async function generate() {
  busy.value = true
  error.value = ''
  try {
    content.value = (await generators[props.kind](props.pid)).content
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

async function save(text) {
  try {
    await api.putArtifact(props.pid, props.kind, text)
    content.value = text
  } catch (e) {
    error.value = e.message
  }
}

onMounted(load)
</script>

<template>
  <div>
    <button :disabled="busy" @click="generate">{{ busy ? '生成中…' : generateLabel }}</button>
    <p v-if="error" class="error">{{ error }}</p>
    <EditorPane v-if="content" :content="content" @save="save" />
    <p v-else class="muted">尚未生成</p>
  </div>
</template>
