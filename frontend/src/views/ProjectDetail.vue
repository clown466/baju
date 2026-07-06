<script setup>
import { onMounted, onUnmounted, provide, ref } from 'vue'
import * as api from '../api'
import { subscribeEvents } from '../sse'
import Skeleton from '../components/Skeleton.vue'
import ArtifactTab from '../tabs/ArtifactTab.vue'
import Stage1Extract from '../tabs/Stage1Extract.vue'
import Stage3Settings from '../tabs/Stage3Settings.vue'
import Stage5Scripts from '../tabs/Stage5Scripts.vue'

const props = defineProps({ pid: { type: String, required: true } })

const project = ref(null)
const tab = ref('stage1')
const error = ref('')
let unsubscribe = null

/* 各阶段完成态（stage5 为最后一步，不判定完成态） */
const stageDone = ref({ stage1: false, stage2: false, stage3: false, stage4: false })
const artifactKinds = { stage2: 'analysis', stage3: 'settings', stage4: 'outline' }

async function checkStageDone() {
  stageDone.value.stage1 =
    !!project.value?.episodes?.some((e) => e.status === 'done')
  for (const [key, kind] of Object.entries(artifactKinds)) {
    try {
      const artifact = await api.getArtifact(props.pid, kind)
      stageDone.value[key] = !!(artifact && artifact.content && artifact.content.trim())
    } catch {
      stageDone.value[key] = false
    }
  }
}

async function refresh() {
  try {
    project.value = await api.getProject(props.pid)
    error.value = ''
    checkStageDone()
  } catch (e) {
    error.value = e.message
  }
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
  ['stage1', '扒剧', '①'],
  ['stage2', '拆解报告', '②'],
  ['stage3', '新剧设定', '③'],
  ['stage4', '大纲', '④'],
  ['stage5', '新剧剧本', '⑤'],
]
</script>

<template>
  <div v-if="project">
    <h1>{{ project.name }}</h1>
    <nav class="tabs">
      <button v-for="[key, label, num] in tabs" :key="key"
              :class="{ active: tab === key }" @click="tab = key">
        <span class="step-num" :class="{ done: stageDone[key] }">{{
          stageDone[key] ? '✓' : num
        }}</span>
        <span class="tab-label">{{ label }}</span>
      </button>
    </nav>
    <Stage1Extract v-if="tab === 'stage1'" :pid="pid" :project="project" />
    <ArtifactTab v-else-if="tab === 'stage2'" :pid="pid" kind="analysis"
                 generate-label="生成拆解报告" />
    <Stage3Settings v-else-if="tab === 'stage3'" :pid="pid" />
    <ArtifactTab v-else-if="tab === 'stage4'" :pid="pid" kind="outline"
                 generate-label="生成逐集大纲" />
    <Stage5Scripts v-else :pid="pid" :project="project" />
  </div>
  <p v-else-if="error" class="error">{{ error }}</p>
  <Skeleton v-else :blocks="4" />
</template>
