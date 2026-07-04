<script>
export default { name: 'Stage1Extract' }
</script>
<script setup>
import { computed, inject, ref } from 'vue'
import * as api from '../api'
import EditorPane from '../components/EditorPane.vue'

const props = defineProps({
  pid: { type: String, required: true },
  project: { type: Object, required: true },
})
const refresh = inject('refresh')

const error = ref('')
const viewing = ref(null)
const script = ref('')
const editingMapping = ref(false)
const mappingDraft = ref([])

const doneCount = computed(
  () => props.project.episodes.filter((e) => e.status === 'done').length)

async function call(fn) {
  error.value = ''
  try {
    await fn()
    await refresh()
  } catch (e) {
    error.value = e.message
  }
}

const start = () => call(() => api.stage1Start(props.pid))
const cancel = () => call(() => api.stage1Cancel(props.pid))
const retry = (ep) => call(() => api.stage1Start(props.pid, [ep]))

function startEditMapping() {
  mappingDraft.value = props.project.episodes.map(
    (e) => ({ episode: e.episode, file: e.file }))
  editingMapping.value = true
}
async function saveMapping() {
  await call(() => api.updateMapping(props.pid, mappingDraft.value))
  editingMapping.value = false
}

async function view(ep) {
  error.value = ''
  try {
    script.value = (await api.getEpisodeScript(props.pid, ep)).content
    viewing.value = ep
  } catch (e) {
    error.value = e.message
  }
}
async function saveScript(text) {
  try {
    await api.putEpisodeScript(props.pid, viewing.value, text)
    script.value = text
  } catch (e) {
    error.value = e.message
  }
}
</script>

<template>
  <div>
    <p>视频目录：{{ project.video_dir }}　｜　完成 {{ doneCount }} / {{ project.episodes.length }}</p>
    <button v-if="!project.running" @click="start">开始扒剧</button>
    <button v-else @click="cancel">取消</button>
    <button v-if="!editingMapping" @click="startEditMapping">调整集数对应</button>
    <button v-else @click="saveMapping">保存集数对应</button>
    <a :href="api.exportUrl(pid, 'original')" target="_blank">导出原剧汇总</a>
    <p v-if="error" class="error">{{ error }}</p>

    <table class="episodes">
      <thead>
        <tr><th>集</th><th>文件</th><th>状态</th><th>操作</th></tr>
      </thead>
      <tbody v-if="editingMapping">
        <tr v-for="(row, i) in mappingDraft" :key="row.file">
          <td><input v-model.number="mappingDraft[i].episode" type="number" /></td>
          <td>{{ row.file }}</td>
          <td></td>
          <td></td>
        </tr>
      </tbody>
      <tbody v-else>
        <tr v-for="e in project.episodes" :key="e.file">
          <td>{{ e.episode }}</td>
          <td>{{ e.file }}</td>
          <td>
            <span :class="`status-${e.status}`">{{ e.status }}</span>
            <span v-if="e.error" class="error">　{{ e.error }}</span>
          </td>
          <td>
            <button v-if="e.status === 'done'" @click="view(e.episode)">查看/编辑</button>
            <button v-if="e.status === 'failed'" @click="retry(e.episode)">重跑</button>
          </td>
        </tr>
      </tbody>
    </table>

    <section v-if="viewing !== null">
      <h2>第 {{ viewing }} 集原剧剧本</h2>
      <EditorPane :content="script" :markdown="false" @save="saveScript" />
    </section>
  </div>
</template>
