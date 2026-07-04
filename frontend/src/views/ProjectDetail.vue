<script setup>
import { onMounted, onUnmounted, provide, ref } from 'vue'
import * as api from '../api'
import { subscribeEvents } from '../sse'
import ArtifactTab from '../tabs/ArtifactTab.vue'
import Stage1Extract from '../tabs/Stage1Extract.vue'
import Stage3Settings from '../tabs/Stage3Settings.vue'
import Stage5Scripts from '../tabs/Stage5Scripts.vue'

const props = defineProps({ pid: { type: String, required: true } })

const project = ref(null)
const tab = ref('stage1')
let unsubscribe = null

async function refresh() {
  project.value = await api.getProject(props.pid)
}
provide('refresh', refresh)

onMounted(async () => {
  await refresh()
  unsubscribe = subscribeEvents(props.pid, async (event) => {
    if (event.type === 'item_done' || event.type === 'batch_done') await refresh()
  })
})
onUnmounted(() => {
  if (unsubscribe) unsubscribe()
})

const tabs = [
  ['stage1', '① 扒剧'],
  ['stage2', '② 拆解报告'],
  ['stage3', '③ 新剧设定'],
  ['stage4', '④ 大纲'],
  ['stage5', '⑤ 新剧剧本'],
]
</script>

<template>
  <div v-if="project">
    <h1>{{ project.name }}</h1>
    <nav class="tabs">
      <button v-for="[key, label] in tabs" :key="key"
              :class="{ active: tab === key }" @click="tab = key">{{ label }}</button>
    </nav>
    <Stage1Extract v-if="tab === 'stage1'" :pid="pid" :project="project" />
    <ArtifactTab v-else-if="tab === 'stage2'" :pid="pid" kind="analysis"
                 generate-label="生成拆解报告" />
    <Stage3Settings v-else-if="tab === 'stage3'" :pid="pid" />
    <ArtifactTab v-else-if="tab === 'stage4'" :pid="pid" kind="outline"
                 generate-label="生成逐集大纲" />
    <Stage5Scripts v-else :pid="pid" :project="project" />
  </div>
  <p v-else class="muted">加载中…</p>
</template>
