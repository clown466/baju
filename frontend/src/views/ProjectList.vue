<script setup>
import { onMounted, ref } from 'vue'
import * as api from '../api'

const projects = ref([])
const name = ref('')
const videoDir = ref('')
const error = ref('')

async function load() {
  try {
    projects.value = await api.listProjects()
    error.value = ''
  } catch (e) {
    error.value = e.message
  }
}

async function create() {
  error.value = ''
  try {
    await api.createProject(name.value, videoDir.value)
    name.value = ''
    videoDir.value = ''
    await load()
  } catch (e) {
    error.value = e.message
  }
}

onMounted(load)
</script>

<template>
  <h1>项目列表</h1>
  <div class="project-grid">
    <router-link v-for="p in projects" :key="p.id"
                 :to="`/projects/${p.id}`" class="project-card">
      <div class="cover">🎬</div>
      <div class="project-card-body">
        <span class="project-name">{{ p.name }}</span>
        <span class="ep-badge">{{ p.episodes.length }} 集</span>
      </div>
    </router-link>
  </div>
  <p v-if="!projects.length" class="muted">暂无项目</p>

  <div class="card new-project-card">
    <h2>新建项目</h2>
    <form @submit.prevent="create">
      <input v-model="name" placeholder="项目名称" required />
      <input v-model="videoDir" placeholder="视频文件夹路径（如 D:\videos\某剧）" required />
      <button type="submit" class="primary">创建并扫描分集</button>
    </form>
    <p v-if="error" class="error">{{ error }}</p>
  </div>
</template>

<style scoped>
.new-project-card {
  max-width: 480px;
  margin-top: var(--sp-4);
}
.new-project-card h2 {
  margin-top: 0;
}
</style>
