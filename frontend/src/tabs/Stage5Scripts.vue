<script>
export default { name: 'Stage5Scripts' }
</script>
<script setup>
import { inject, ref } from 'vue'
import * as api from '../api'
import EditorPane from '../components/EditorPane.vue'
import { useToast } from '../composables/useToast'

const props = defineProps({
  pid: { type: String, required: true },
  project: { type: Object, required: true },
})
const refresh = inject('refresh')
const toast = useToast()

const extra = ref('')
const error = ref('')
const viewing = ref(null)
const script = ref('')
const busyEp = ref(null)

async function startBatch() {
  error.value = ''
  try {
    await api.stage5Start(props.pid, null, extra.value)
    await refresh()
  } catch (e) {
    error.value = e.message
  }
}

async function cancel() {
  error.value = ''
  try {
    await api.stage1Cancel(props.pid)
    await refresh()
  } catch (e) {
    error.value = e.message
  }
}

async function genOne(ep) {
  error.value = ''
  busyEp.value = ep
  try {
    script.value = (await api.stage5Generate(props.pid, ep, extra.value)).content
    viewing.value = ep
  } catch (e) {
    error.value = e.message
  } finally {
    busyEp.value = null
  }
}

async function view(ep) {
  error.value = ''
  try {
    script.value = (await api.getNewScript(props.pid, ep)).content
    viewing.value = ep
  } catch (e) {
    error.value = e.message
  }
}

async function saveScript(text) {
  try {
    await api.putNewScript(props.pid, viewing.value, text)
    script.value = text
    toast.success('已保存')
  } catch (e) {
    error.value = e.message
  }
}
</script>

<template>
  <div>
    <textarea v-model="extra" rows="2"
              placeholder="附加指令（可选，如：台词更口语化）"></textarea>
    <button :disabled="project.running" @click="startBatch">批量生成全部</button>
    <button v-if="project.running" @click="cancel">取消</button>
    <a :href="api.exportUrl(pid, 'new')" target="_blank">导出新剧汇总</a>
    <p v-if="project.running" class="muted">批量生成中（为保证前后集衔接按集串行）…</p>
    <p v-if="error" class="error">{{ error }}</p>

    <table class="episodes">
      <thead>
        <tr><th>集</th><th>状态</th><th>操作</th></tr>
      </thead>
      <tbody>
        <tr v-for="e in project.episodes" :key="e.episode">
          <td>第 {{ e.episode }} 集</td>
          <td>
            <span v-if="busyEp === e.episode" class="badge running status-running">running</span>
            <span v-else-if="project.running" class="badge pending status-pending">queued</span>
            <span v-else class="muted">—</span>
          </td>
          <td>
            <button :disabled="busyEp !== null || project.running" @click="genOne(e.episode)">
              {{ busyEp === e.episode ? '生成中…' : '生成/重生成' }}
            </button>
            <button @click="view(e.episode)">查看</button>
          </td>
        </tr>
      </tbody>
    </table>

    <section v-if="viewing !== null">
      <h2>新剧第 {{ viewing }} 集</h2>
      <EditorPane :content="script" :markdown="false" @save="saveScript" />
    </section>
  </div>
</template>
