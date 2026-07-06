<script>
export default { name: 'Stage3Settings' }
</script>
<script setup>
import { onMounted, ref } from 'vue'
import * as api from '../api'
import EditorPane from '../components/EditorPane.vue'
import MarkdownView from '../components/MarkdownView.vue'
import { useToast } from '../composables/useToast'

const props = defineProps({ pid: { type: String, required: true } })
const toast = useToast()

const suggestions = ref('')
const draft = ref('')
const settings = ref('')
const busy = ref('')
const error = ref('')

async function load() {
  try {
    settings.value = (await api.getArtifact(props.pid, 'settings')).content
  } catch {
    settings.value = ''
  }
}

async function suggest() {
  busy.value = 'suggest'
  error.value = ''
  try {
    suggestions.value = (await api.stage3Suggest(props.pid)).content
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = ''
  }
}

async function refine() {
  busy.value = 'refine'
  error.value = ''
  try {
    settings.value = (await api.stage3Refine(props.pid, draft.value)).content
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = ''
  }
}

async function save(text) {
  try {
    await api.putArtifact(props.pid, 'settings', text)
    settings.value = text
    toast.success('已保存')
  } catch (e) {
    error.value = e.message
  }
}

onMounted(load)
</script>

<template>
  <div>
    <section>
      <h2>题材建议</h2>
      <button :disabled="busy !== ''" @click="suggest">
        {{ busy === 'suggest' ? '生成中…' : 'AI 建议新题材' }}
      </button>
      <MarkdownView v-if="suggestions" :content="suggestions" />
    </section>

    <section>
      <h2>设定草稿</h2>
      <textarea v-model="draft" rows="10"
                placeholder="新题材 / 世界观 / 人物与新旧人物映射表（自由文本，可参考上方 AI 建议）"></textarea>
      <button :disabled="busy !== ''" @click="refine">
        {{ busy === 'refine' ? '完善中…' : 'AI 完善设定' }}
      </button>
    </section>

    <p v-if="error" class="error">{{ error }}</p>

    <section>
      <h2>新剧设定</h2>
      <EditorPane v-if="settings" :content="settings" @save="save" />
      <p v-else class="muted">尚未生成</p>
    </section>
  </div>
</template>
