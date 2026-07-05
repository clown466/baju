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
  <p><router-link to="/settings">⚙ 模型设置</router-link></p>
  <ul class="projects">
    <li v-for="p in projects" :key="p.id">
      <router-link :to="`/projects/${p.id}`">{{ p.name }}</router-link>
      <span class="muted">　{{ p.episodes.length }} 集</span>
    </li>
  </ul>
  <p v-if="!projects.length" class="muted">暂无项目</p>

  <h2>新建项目</h2>
  <form @submit.prevent="create">
    <input v-model="name" placeholder="项目名称" required />
    <input v-model="videoDir" placeholder="视频文件夹路径（如 D:\videos\某剧）" required />
    <button type="submit">创建并扫描分集</button>
  </form>
  <p v-if="error" class="error">{{ error }}</p>
</template>
