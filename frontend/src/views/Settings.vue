<script setup>
import { onMounted, reactive, ref } from 'vue'
import * as api from '../api'
import { useConfirm } from '../composables/useConfirm'
import { useToast } from '../composables/useToast'

const toast = useToast()
const { confirm } = useConfirm()

const gemini = ref(null)
const textLlm = ref(null)
const newProvider = ref('')
const error = ref('')
const saved = ref(false)
const busy = ref(false)

/* 密钥显隐（key: 'gemini' 或服务商名） */
const showKey = reactive({})
function toggleKey(name) {
  showKey[name] = !showKey[name]
}

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

async function removeProvider(name) {
  if (name === textLlm.value.provider) {
    error.value = '不能删除当前使用中的服务商'
    return
  }
  if (!(await confirm(`确定删除服务商 ${name}？`))) return
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
    toast.success('设置已保存并立即生效')
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

onMounted(load)
</script>

<template>
  <!-- 单根：让 App.vue 路由 <Transition> 可以直接做淡入淡出 -->
  <div>
  <p><router-link to="/">← 返回项目列表</router-link></p>
  <h1>模型设置</h1>

  <template v-if="gemini && textLlm">
    <h2>视频识别（阶段① Gemini）</h2>
    <div class="form-grid">
      <label>API 密钥
        <span class="key-field">
          <input v-model="gemini.api_key" :type="showKey.gemini ? 'text' : 'password'" />
          <button type="button" class="eye" aria-label="显示/隐藏密钥"
                  :title="showKey.gemini ? '隐藏密钥' : '显示密钥'"
                  @click="toggleKey('gemini')">👁</button>
        </span>
      </label>
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
        <label>API 密钥
          <span class="key-field">
            <input v-model="p.api_key" :type="showKey[name] ? 'text' : 'password'" />
            <button type="button" class="eye" aria-label="显示/隐藏密钥"
                    :title="showKey[name] ? '隐藏密钥' : '显示密钥'"
                    @click="toggleKey(name)">👁</button>
          </span>
        </label>
        <label>模型名 <input v-model="p.model" /></label>
      </div>
    </div>

    <p>
      <input v-model="newProvider" class="new-provider" placeholder="服务商名称（如 deepseek）" />
      <button type="button" @click="addProvider">新增服务商</button>
    </p>

    <p>
      <button type="button" class="primary" :class="{ loading: busy }" :disabled="busy" @click="save">保存设置</button>
      <span v-if="saved" class="muted">　已保存并立即生效</span>
    </p>
  </template>
  <p v-else-if="!error" class="muted">加载中…</p>
  <p v-if="error" class="error">{{ error }}</p>
  </div>
</template>

<style scoped>
.form-grid { display: grid; gap: var(--sp-2); max-width: 640px; }
.form-grid label { display: flex; flex-direction: column; gap: var(--sp-1); }
.provider-card {
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg-card);
  box-shadow: var(--shadow-card);
  padding: var(--sp-2) var(--sp-3);
  margin: var(--sp-2) 0;
  max-width: 640px;
}
.provider-card h3 { display: flex; justify-content: space-between; align-items: center; margin: var(--sp-1) 0; }

.key-field {
  position: relative;
  display: flex;
  align-items: center;
}
.key-field input {
  padding-right: var(--sp-5);
}
.key-field .eye {
  position: absolute;
  right: var(--sp-1);
  margin: 0;
  padding: 0 var(--sp-1);
  border: none;
  background: none;
  color: var(--text-secondary);
  line-height: 1;
}
.key-field .eye:hover {
  color: var(--accent);
  border: none;
  background: none;
}
</style>
