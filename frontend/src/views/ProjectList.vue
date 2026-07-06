<script setup>
import { onMounted, ref } from 'vue'
import * as api from '../api'
import Skeleton from '../components/Skeleton.vue'

const projects = ref([])
const name = ref('')
const videoDir = ref('')
const error = ref('')
const loading = ref(true)

async function load() {
  try {
    projects.value = await api.listProjects()
    error.value = ''
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
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
  <Skeleton v-if="loading" :blocks="3" />
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
  <div v-if="!loading && !projects.length" class="empty-state">
    <div class="empty-icon">🎬</div>
    <p class="empty-title">还没有项目</p>
    <p class="muted">暂无项目，在下方表单填写视频文件夹，创建第一个项目吧</p>
  </div>

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
