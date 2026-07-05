<script setup>
import { onMounted, ref } from 'vue'
import * as api from '../api'

const gemini = ref(null)
const textLlm = ref(null)
const newProvider = ref('')
const error = ref('')
const saved = ref(false)
const busy = ref(false)

async function load() {
  try {
    const s = await api.getSettings()
    gemini.value = s.gemini
    textLlm.value = s.text_llm
    error.value = ''
  } catch (e) {
    error.value = e.message
  }
}

function addProvider() {
  const name = newProvider.value.trim()
  if (!name) return
  if (!textLlm.value.providers[name]) {
    textLlm.value.providers[name] = { base_url: '', api_key: '', model: '' }
  }
  newProvider.value = ''
}

function removeProvider(name) {
  if (name === textLlm.value.provider) {
    error.value = '不能删除当前使用中的服务商'
    return
  }
  delete textLlm.value.providers[name]
}

async function save() {
  error.value = ''
  saved.value = false
  busy.value = true
  try {
    const s = await api.putSettings({
      gemini: { ...gemini.value, base_url: gemini.value.base_url || null },
      text_llm: textLlm.value,
    })
    gemini.value = s.gemini
    textLlm.value = s.text_llm
    saved.value = true
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

onMounted(load)
</script>

<template>
  <p><router-link to="/">← 返回项目列表</router-link></p>
  <h1>模型设置</h1>

  <template v-if="gemini && textLlm">
    <h2>视频识别（阶段① Gemini）</h2>
    <div class="form-grid">
      <label>API 密钥 <input v-model="gemini.api_key" /></label>
      <label>模型名 <input v-model="gemini.model" /></label>
      <label>中转地址（留空走 Google 官方）
        <input v-model="gemini.base_url" placeholder="https://your-proxy.example.com" />
      </label>
      <label>上传方式
        <select v-model="gemini.upload">
          <option value="files">Files API（原生密钥，无大小限制）</option>
          <option value="inline">内联上传（中转站，单集 ≤19MB）</option>
        </select>
      </label>
    </div>

    <h2>文本生成（阶段②-⑤）</h2>
    <label>当前服务商
      <select v-model="textLlm.provider" class="provider-select">
        <option v-for="(p, name) in textLlm.providers" :key="name" :value="name">
          {{ name }}
        </option>
      </select>
    </label>

    <div v-for="(p, name) in textLlm.providers" :key="name" class="provider-card">
      <h3>{{ name }}
        <button type="button" class="danger" @click="removeProvider(name)">删除</button>
      </h3>
      <div class="form-grid">
        <label>接口地址 <input v-model="p.base_url" placeholder="https://api.example.com/v1" /></label>
        <label>API 密钥 <input v-model="p.api_key" /></label>
        <label>模型名 <input v-model="p.model" /></label>
      </div>
    </div>

    <p>
      <input v-model="newProvider" class="new-provider" placeholder="服务商名称（如 deepseek）" />
      <button type="button" @click="addProvider">新增服务商</button>
    </p>

    <p>
      <button type="button" :disabled="busy" @click="save">保存设置</button>
      <span v-if="saved" class="muted">　已保存并立即生效</span>
    </p>
  </template>
  <p v-else-if="!error" class="muted">加载中…</p>
  <p v-if="error" class="error">{{ error }}</p>
</template>

<style scoped>
.form-grid { display: grid; gap: 8px; max-width: 640px; }
.form-grid label { display: flex; flex-direction: column; gap: 2px; }
.provider-card { border: 1px solid #ddd; border-radius: 6px; padding: 8px 12px; margin: 8px 0; max-width: 640px; }
.provider-card h3 { display: flex; justify-content: space-between; align-items: center; margin: 4px 0; }
button.danger { background: #c0392b; }
</style>
