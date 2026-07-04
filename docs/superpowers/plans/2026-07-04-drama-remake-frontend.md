# 短剧扒剧与仿写 — 前端 Web 界面实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为已完成的 FastAPI 后端构建 Vue 3 + Vite 本地 Web 界面：项目列表 + 五个阶段页签（①扒剧 ②拆解报告 ③新剧设定 ④大纲 ⑤新剧剧本），SSE 实时进度。

**Architecture:** 单页应用（vue-router hash 路由），`src/api.js` 封装全部后端调用，`src/sse.js` 封装 SSE 订阅；`ProjectDetail.vue` 负责项目数据与 SSE 刷新，五个页签组件只做各自阶段的交互；②④共用一个 `ArtifactTab.vue`（生成+查看/编辑产物）。

**Tech Stack:** Vue 3、Vite 5、vue-router 4、marked + dompurify（Markdown 渲染）、Vitest + @vue/test-utils + jsdom（测试）。

## Global Constraints

- 前端根目录 `frontend/`，与 `backend/` 平级；需要 Node.js ≥ 18（`node --version` 验证，缺失即 BLOCKED 上报）
- 后端 API 前缀 `/api`，开发时由 Vite 代理到 `http://127.0.0.1:8000`（后端启动方式：`cd backend && python -m app.main`）
- 后端错误响应格式：`{"detail": "中文错误信息"}`，HTTP 状态 400/404/409
- SSE 端点 `GET /api/projects/{pid}/events`，事件负载（精确）：`{"type":"item_done","item":<集号int>,"ok":<bool>,"error":"<str，仅失败时>"}` 与 `{"type":"batch_done"}`；每 15 秒发注释行 `: keepalive`
- 集状态枚举：`pending / uploading / analyzing / done / failed`
- 项目 ID 为 8 位十六进制字符串；`GET /api/projects/{pid}` 返回 `{id, name, video_dir, episodes: [{episode, file, status, error}], running: <bool>}`
- 所有界面文案使用中文；不引入 UI 组件库（原生 HTML + 少量 CSS）
- 测试命令：`cd frontend && npm test`（vitest run，jsdom 环境）
- 提交信息用中文 conventional commits（`feat:` / `test:` / `docs:`）

### 后端 API 一览（api.js 必须逐一覆盖）

| 方法 | 路径 | 请求体 | 响应 |
|------|------|--------|------|
| POST | `/api/projects` | `{name, video_dir}` | project 对象 |
| GET | `/api/projects` | - | project 数组 |
| GET | `/api/projects/{pid}` | - | project + episodes 状态 + running |
| PUT | `/api/projects/{pid}/episodes-mapping` | `{episodes: [{episode, file}]}` | `{ok}` |
| POST | `/api/projects/{pid}/stage1/start` | `{episodes: [int] \| null}` | `{started}` |
| POST | `/api/projects/{pid}/stage1/cancel` | - | `{ok}`（取消该项目当前批次，阶段⑤批量也用它） |
| GET/PUT | `/api/projects/{pid}/episodes/{ep}/script` | PUT: `{content}` | `{content}` / `{ok}` |
| POST | `/api/projects/{pid}/stage2/generate` | - | `{content}` |
| POST | `/api/projects/{pid}/stage3/suggest` | - | `{content}`（不落盘） |
| POST | `/api/projects/{pid}/stage3/refine` | `{draft}` | `{content}` |
| POST | `/api/projects/{pid}/stage4/generate` | - | `{content}` |
| POST | `/api/projects/{pid}/stage5/generate` | `{episode, extra}` | `{content}` |
| POST | `/api/projects/{pid}/stage5/start` | `{episodes: [int] \| null, extra}` | `{started}` |
| GET/PUT | `/api/projects/{pid}/artifacts/{kind}` | kind ∈ analysis/settings/outline；PUT: `{content}` | `{content}` / `{ok}` |
| GET/PUT | `/api/projects/{pid}/scripts/{ep}` | PUT: `{content}` | `{content}` / `{ok}` |
| GET | `/api/projects/{pid}/export?which=original\|new` | - | text/plain 全剧汇总 |
| GET | `/api/projects/{pid}/events` | - | SSE 流 |

### 文件结构

```
frontend/
├── package.json
├── vite.config.js          # vue 插件 + /api 代理 + vitest jsdom 配置
├── index.html
├── README.md               # Task 10
├── src/
│   ├── main.js
│   ├── style.css
│   ├── App.vue             # 顶栏 + router-view
│   ├── router.js           # / → ProjectList，/projects/:pid → ProjectDetail
│   ├── api.js              # 全部后端调用（唯一 fetch 出口）
│   ├── sse.js              # SSE 订阅（唯一 EventSource 出口）
│   ├── components/
│   │   ├── MarkdownView.vue    # marked + dompurify 渲染
│   │   └── EditorPane.vue      # 查看/编辑切换 + 保存（emit save）
│   ├── views/
│   │   ├── ProjectList.vue     # 列表 + 新建（填路径→后端扫描）
│   │   └── ProjectDetail.vue   # 项目加载 + 页签 + SSE 刷新 + provide('refresh')
│   └── tabs/
│       ├── Stage1Extract.vue   # ①分集表/开始/取消/重跑/映射编辑/查看编辑/导出
│       ├── ArtifactTab.vue     # ②拆解报告 与 ④大纲 共用
│       ├── Stage3Settings.vue  # ③建议/草稿/AI完善/查看编辑
│       └── Stage5Scripts.vue   # ⑤批量/单集生成/查看编辑/导出
└── tests/
    ├── app.test.js
    ├── api.test.js
    ├── sse.test.js
    ├── components.test.js
    ├── project-list.test.js
    ├── project-detail.test.js
    ├── stage1.test.js
    ├── artifact-stage3.test.js
    └── stage5.test.js
```

---

### Task 1: 前端脚手架与路由壳

**Files:**
- Create: `frontend/package.json`、`frontend/vite.config.js`、`frontend/index.html`、`frontend/src/main.js`、`frontend/src/style.css`、`frontend/src/App.vue`、`frontend/src/router.js`、`frontend/src/views/ProjectList.vue`（占位）、`frontend/src/views/ProjectDetail.vue`（占位）
- Test: `frontend/tests/app.test.js`

**Interfaces:**
- Produces: 可运行的 Vite + Vitest 工程；路由 `/`（ProjectList）与 `/projects/:pid`（ProjectDetail，props: pid）；后续任务重写两个占位视图

- [ ] **Step 0: 验证 Node 环境**

Run: `node --version && npm --version`
Expected: Node ≥ 18。若命令不存在，停止并以 BLOCKED 上报（本机未装 Node.js）。

- [ ] **Step 1: 创建 package.json**

```json
{
  "name": "drama-remake-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "test": "vitest run"
  },
  "dependencies": {
    "dompurify": "^3.1.0",
    "marked": "^12.0.0",
    "vue": "^3.4.0",
    "vue-router": "^4.3.0"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.0.0",
    "@vue/test-utils": "^2.4.0",
    "jsdom": "^24.0.0",
    "vite": "^5.2.0",
    "vitest": "^1.5.0"
  }
}
```

- [ ] **Step 2: 创建 vite.config.js**

```js
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
  test: {
    environment: 'jsdom',
    globals: true,
  },
})
```

- [ ] **Step 3: 创建 index.html**

```html
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>短剧扒剧与仿写</title>
</head>
<body>
  <div id="app"></div>
  <script type="module" src="/src/main.js"></script>
</body>
</html>
```

- [ ] **Step 4: 创建 src/main.js 与 src/style.css**

`src/main.js`:

```js
import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import './style.css'

createApp(App).use(router).mount('#app')
```

`src/style.css`:

```css
body { margin: 0; font-family: system-ui, "Microsoft YaHei", sans-serif; color: #222; }
.topbar { padding: 12px 24px; background: #1f2733; }
.topbar a { color: #fff; text-decoration: none; font-weight: 600; }
main { max-width: 960px; margin: 0 auto; padding: 16px 24px 64px; }
button { margin: 2px 4px 2px 0; padding: 4px 12px; cursor: pointer; }
button:disabled { cursor: not-allowed; opacity: 0.5; }
input, textarea { width: 100%; box-sizing: border-box; padding: 6px 8px; margin: 4px 0; }
table.episodes { width: 100%; border-collapse: collapse; margin-top: 12px; }
table.episodes th, table.episodes td { border: 1px solid #ddd; padding: 6px 8px; text-align: left; }
.tabs { margin: 12px 0; border-bottom: 2px solid #ddd; }
.tabs button { border: none; background: none; padding: 8px 16px; }
.tabs button.active { border-bottom: 2px solid #1f2733; font-weight: 600; }
.error { color: #c0392b; }
.muted { color: #888; }
.status-done { color: #27ae60; }
.status-failed { color: #c0392b; }
.status-analyzing, .status-uploading { color: #e67e22; }
.markdown { line-height: 1.7; }
textarea { font-family: inherit; }
```

- [ ] **Step 5: 创建 src/App.vue**

```vue
<template>
  <header class="topbar">
    <router-link to="/">短剧扒剧与仿写</router-link>
  </header>
  <main><router-view /></main>
</template>
```

- [ ] **Step 6: 创建 src/router.js**

```js
import { createRouter, createWebHashHistory } from 'vue-router'
import ProjectDetail from './views/ProjectDetail.vue'
import ProjectList from './views/ProjectList.vue'

export default createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', component: ProjectList },
    { path: '/projects/:pid', component: ProjectDetail, props: true },
  ],
})
```

- [ ] **Step 7: 创建两个占位视图**

`src/views/ProjectList.vue`:

```vue
<template>
  <h1>项目列表</h1>
</template>
```

`src/views/ProjectDetail.vue`:

```vue
<script setup>
defineProps({ pid: { type: String, required: true } })
</script>
<template>
  <h1>项目详情</h1>
</template>
```

- [ ] **Step 8: 写冒烟测试 frontend/tests/app.test.js**

```js
import { mount } from '@vue/test-utils'
import { expect, test } from 'vitest'
import App from '../src/App.vue'

test('渲染顶栏标题', () => {
  const wrapper = mount(App, {
    global: { stubs: { RouterLink: { template: '<a><slot /></a>' }, RouterView: true } },
  })
  expect(wrapper.text()).toContain('短剧扒剧与仿写')
})
```

- [ ] **Step 9: 安装依赖并运行测试**

Run: `cd frontend && npm install && npm test`
Expected: 1 passed

- [ ] **Step 10: 验证构建**

Run: `cd frontend && npm run build`
Expected: 生成 `frontend/dist/`，无报错。不要提交 dist（下一步加 .gitignore 规则）。

- [ ] **Step 11: 追加 .gitignore 规则**

在仓库根 `.gitignore` 末尾追加：

```
frontend/node_modules/
frontend/dist/
```

- [ ] **Step 12: Commit**

```bash
git add .gitignore frontend/package.json frontend/package-lock.json frontend/vite.config.js frontend/index.html frontend/src frontend/tests
git commit -m "feat: 前端脚手架与路由壳"
```

---

### Task 2: API 客户端 api.js

**Files:**
- Create: `frontend/src/api.js`
- Test: `frontend/tests/api.test.js`

**Interfaces:**
- Produces（后续所有组件依赖，签名必须一字不差）:
  - `listProjects()`、`createProject(name, videoDir)`、`getProject(pid)`
  - `updateMapping(pid, episodes)`（episodes: `[{episode, file}]`）
  - `stage1Start(pid, episodes = null)`、`stage1Cancel(pid)`
  - `getEpisodeScript(pid, ep)`、`putEpisodeScript(pid, ep, content)`
  - `stage2Generate(pid)`、`stage3Suggest(pid)`、`stage3Refine(pid, draft)`、`stage4Generate(pid)`
  - `stage5Generate(pid, episode, extra = '')`、`stage5Start(pid, episodes = null, extra = '')`
  - `getArtifact(pid, kind)`、`putArtifact(pid, kind, content)`
  - `getNewScript(pid, ep)`、`putNewScript(pid, ep, content)`
  - `exportUrl(pid, which)` → 字符串（不发请求）
  - 所有请求函数：非 2xx 时 `throw new Error(detail)`（detail 取自响应 JSON 的 `detail` 字段，取不到则用 statusText）

- [ ] **Step 1: 写失败测试 frontend/tests/api.test.js**

```js
import { afterEach, expect, test, vi } from 'vitest'
import * as api from '../src/api'

function mockFetch(body, ok = true, status = 200) {
  const res = {
    ok,
    status,
    statusText: 'HTTP ' + status,
    headers: new Headers({ 'content-type': 'application/json' }),
    json: async () => body,
    text: async () => JSON.stringify(body),
  }
  const fn = vi.fn(async () => res)
  vi.stubGlobal('fetch', fn)
  return fn
}

afterEach(() => vi.unstubAllGlobals())

test('createProject 发送 POST JSON', async () => {
  const fn = mockFetch({ id: 'abc12345' })
  const out = await api.createProject('测试', 'D:/videos')
  expect(fn.mock.calls[0][0]).toBe('/api/projects')
  expect(fn.mock.calls[0][1].method).toBe('POST')
  expect(JSON.parse(fn.mock.calls[0][1].body)).toEqual({ name: '测试', video_dir: 'D:/videos' })
  expect(out.id).toBe('abc12345')
})

test('getProject 发送 GET', async () => {
  const fn = mockFetch({ id: 'deadbeef', episodes: [] })
  await api.getProject('deadbeef')
  expect(fn.mock.calls[0][0]).toBe('/api/projects/deadbeef')
  expect(fn.mock.calls[0][1].method).toBe('GET')
})

test('非 2xx 抛出 detail 错误', async () => {
  mockFetch({ detail: '项目不存在' }, false, 404)
  await expect(api.getProject('deadbeef')).rejects.toThrow('项目不存在')
})

test('updateMapping 发送 episodes 数组', async () => {
  const fn = mockFetch({ ok: true })
  await api.updateMapping('deadbeef', [{ episode: 1, file: 'a.mp4' }])
  expect(fn.mock.calls[0][0]).toBe('/api/projects/deadbeef/episodes-mapping')
  expect(JSON.parse(fn.mock.calls[0][1].body)).toEqual({ episodes: [{ episode: 1, file: 'a.mp4' }] })
})

test('stage1Start 默认 episodes 为 null', async () => {
  const fn = mockFetch({ started: [1] })
  await api.stage1Start('deadbeef')
  expect(fn.mock.calls[0][0]).toBe('/api/projects/deadbeef/stage1/start')
  expect(JSON.parse(fn.mock.calls[0][1].body)).toEqual({ episodes: null })
})

test('stage3Refine 发送 draft', async () => {
  const fn = mockFetch({ content: '设定' })
  await api.stage3Refine('deadbeef', '草稿')
  expect(fn.mock.calls[0][0]).toBe('/api/projects/deadbeef/stage3/refine')
  expect(JSON.parse(fn.mock.calls[0][1].body)).toEqual({ draft: '草稿' })
})

test('stage5Start 传 episodes 与 extra', async () => {
  const fn = mockFetch({ started: [1, 2] })
  await api.stage5Start('deadbeef', [1, 2], '台词更口语化')
  expect(fn.mock.calls[0][0]).toBe('/api/projects/deadbeef/stage5/start')
  expect(JSON.parse(fn.mock.calls[0][1].body)).toEqual({ episodes: [1, 2], extra: '台词更口语化' })
})

test('putArtifact 与 getNewScript 路径正确', async () => {
  let fn = mockFetch({ ok: true })
  await api.putArtifact('deadbeef', 'settings', '内容')
  expect(fn.mock.calls[0][0]).toBe('/api/projects/deadbeef/artifacts/settings')
  fn = mockFetch({ content: '剧本' })
  await api.getNewScript('deadbeef', 3)
  expect(fn.mock.calls[0][0]).toBe('/api/projects/deadbeef/scripts/3')
})

test('exportUrl 拼接 which 参数', () => {
  expect(api.exportUrl('deadbeef', 'new')).toBe('/api/projects/deadbeef/export?which=new')
  expect(api.exportUrl('deadbeef', 'original')).toBe('/api/projects/deadbeef/export?which=original')
})
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd frontend && npm test`
Expected: FAIL（`../src/api` 不存在）

- [ ] **Step 3: 实现 frontend/src/api.js**

```js
async function http(method, url, body) {
  const opts = { method, headers: {} }
  if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json'
    opts.body = JSON.stringify(body)
  }
  const res = await fetch(url, opts)
  if (!res.ok) {
    let detail = res.statusText
    try {
      detail = (await res.json()).detail || detail
    } catch { /* 非 JSON 响应，保留 statusText */ }
    throw new Error(detail)
  }
  return res.json()
}

export const listProjects = () => http('GET', '/api/projects')
export const createProject = (name, videoDir) =>
  http('POST', '/api/projects', { name, video_dir: videoDir })
export const getProject = (pid) => http('GET', `/api/projects/${pid}`)
export const updateMapping = (pid, episodes) =>
  http('PUT', `/api/projects/${pid}/episodes-mapping`, { episodes })

export const stage1Start = (pid, episodes = null) =>
  http('POST', `/api/projects/${pid}/stage1/start`, { episodes })
export const stage1Cancel = (pid) => http('POST', `/api/projects/${pid}/stage1/cancel`)

export const getEpisodeScript = (pid, ep) =>
  http('GET', `/api/projects/${pid}/episodes/${ep}/script`)
export const putEpisodeScript = (pid, ep, content) =>
  http('PUT', `/api/projects/${pid}/episodes/${ep}/script`, { content })

export const stage2Generate = (pid) => http('POST', `/api/projects/${pid}/stage2/generate`)
export const stage3Suggest = (pid) => http('POST', `/api/projects/${pid}/stage3/suggest`)
export const stage3Refine = (pid, draft) =>
  http('POST', `/api/projects/${pid}/stage3/refine`, { draft })
export const stage4Generate = (pid) => http('POST', `/api/projects/${pid}/stage4/generate`)

export const stage5Generate = (pid, episode, extra = '') =>
  http('POST', `/api/projects/${pid}/stage5/generate`, { episode, extra })
export const stage5Start = (pid, episodes = null, extra = '') =>
  http('POST', `/api/projects/${pid}/stage5/start`, { episodes, extra })

export const getArtifact = (pid, kind) => http('GET', `/api/projects/${pid}/artifacts/${kind}`)
export const putArtifact = (pid, kind, content) =>
  http('PUT', `/api/projects/${pid}/artifacts/${kind}`, { content })

export const getNewScript = (pid, ep) => http('GET', `/api/projects/${pid}/scripts/${ep}`)
export const putNewScript = (pid, ep, content) =>
  http('PUT', `/api/projects/${pid}/scripts/${ep}`, { content })

export const exportUrl = (pid, which) => `/api/projects/${pid}/export?which=${which}`
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd frontend && npm test`
Expected: 全部通过（含 Task 1 的 1 个）

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api.js frontend/tests/api.test.js
git commit -m "feat: API 客户端封装"
```

---

### Task 3: SSE 订阅 sse.js

**Files:**
- Create: `frontend/src/sse.js`
- Test: `frontend/tests/sse.test.js`

**Interfaces:**
- Produces: `subscribeEvents(pid, onEvent)` → 返回取消函数；对每条 SSE 消息 `JSON.parse` 后回调 `onEvent(event)`，解析失败静默忽略

- [ ] **Step 1: 写失败测试 frontend/tests/sse.test.js**

```js
import { afterEach, expect, test, vi } from 'vitest'
import { subscribeEvents } from '../src/sse'

class FakeEventSource {
  static last = null
  constructor(url) {
    this.url = url
    this.onmessage = null
    this.closed = false
    FakeEventSource.last = this
  }
  close() { this.closed = true }
}

afterEach(() => vi.unstubAllGlobals())

test('订阅、解析事件、取消关闭', () => {
  vi.stubGlobal('EventSource', FakeEventSource)
  const events = []
  const stop = subscribeEvents('deadbeef', (e) => events.push(e))
  const es = FakeEventSource.last
  expect(es.url).toBe('/api/projects/deadbeef/events')
  es.onmessage({ data: '{"type":"item_done","item":3,"ok":true}' })
  es.onmessage({ data: '{"type":"batch_done"}' })
  es.onmessage({ data: 'not-json' })
  expect(events).toEqual([
    { type: 'item_done', item: 3, ok: true },
    { type: 'batch_done' },
  ])
  stop()
  expect(es.closed).toBe(true)
})
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd frontend && npm test`
Expected: FAIL（`../src/sse` 不存在）

- [ ] **Step 3: 实现 frontend/src/sse.js**

```js
export function subscribeEvents(pid, onEvent) {
  const es = new EventSource(`/api/projects/${pid}/events`)
  es.onmessage = (e) => {
    if (!e.data) return
    let event
    try {
      event = JSON.parse(e.data)
    } catch {
      return
    }
    onEvent(event)
  }
  return () => es.close()
}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd frontend && npm test`
Expected: 全部通过

- [ ] **Step 5: Commit**

```bash
git add frontend/src/sse.js frontend/tests/sse.test.js
git commit -m "feat: SSE 事件订阅"
```

---

### Task 4: 通用组件 MarkdownView 与 EditorPane

**Files:**
- Create: `frontend/src/components/MarkdownView.vue`、`frontend/src/components/EditorPane.vue`
- Test: `frontend/tests/components.test.js`

**Interfaces:**
- Produces:
  - `MarkdownView`：props `{content: String}`，渲染净化后的 Markdown HTML
  - `EditorPane`：props `{content: String, markdown: Boolean = true}`，emits `save(text)`；查看态渲染 Markdown（`markdown=false` 时用 `<pre>` 原文），点「编辑」切 textarea，点「保存」emit 并回到查看态

- [ ] **Step 1: 写失败测试 frontend/tests/components.test.js**

```js
import { mount } from '@vue/test-utils'
import { expect, test } from 'vitest'
import EditorPane from '../src/components/EditorPane.vue'
import MarkdownView from '../src/components/MarkdownView.vue'

test('MarkdownView 渲染 Markdown', () => {
  const wrapper = mount(MarkdownView, { props: { content: '**加粗**' } })
  expect(wrapper.html()).toContain('<strong>加粗</strong>')
})

test('MarkdownView 过滤脚本注入', () => {
  const wrapper = mount(MarkdownView, {
    props: { content: '<script>alert(1)</' + 'script>正文' },
  })
  expect(wrapper.html()).not.toContain('<script>')
  expect(wrapper.text()).toContain('正文')
})

test('EditorPane 查看态渲染内容，编辑后保存 emit', async () => {
  const wrapper = mount(EditorPane, { props: { content: '# 标题' } })
  expect(wrapper.html()).toContain('<h1>标题</h1>')
  await wrapper.findAll('button').find((b) => b.text() === '编辑').trigger('click')
  await wrapper.find('textarea').setValue('新内容')
  await wrapper.findAll('button').find((b) => b.text() === '保存').trigger('click')
  expect(wrapper.emitted('save')[0]).toEqual(['新内容'])
  expect(wrapper.find('textarea').exists()).toBe(false)
})

test('EditorPane markdown=false 用纯文本渲染', () => {
  const wrapper = mount(EditorPane, { props: { content: '1-1 日 内 客厅', markdown: false } })
  expect(wrapper.find('pre.plain').text()).toContain('1-1 日 内 客厅')
})
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd frontend && npm test`
Expected: FAIL（组件不存在）

- [ ] **Step 3: 实现 frontend/src/components/MarkdownView.vue**

```vue
<script setup>
import DOMPurify from 'dompurify'
import { marked } from 'marked'
import { computed } from 'vue'

const props = defineProps({ content: { type: String, default: '' } })
const html = computed(() => DOMPurify.sanitize(marked.parse(props.content)))
</script>

<template>
  <div class="markdown" v-html="html"></div>
</template>
```

- [ ] **Step 4: 实现 frontend/src/components/EditorPane.vue**

```vue
<script setup>
import { ref, watch } from 'vue'
import MarkdownView from './MarkdownView.vue'

const props = defineProps({
  content: { type: String, default: '' },
  markdown: { type: Boolean, default: true },
})
const emit = defineEmits(['save'])

const editing = ref(false)
const draft = ref(props.content)
watch(() => props.content, (v) => {
  if (!editing.value) draft.value = v
})

function startEdit() {
  draft.value = props.content
  editing.value = true
}
function save() {
  emit('save', draft.value)
  editing.value = false
}
</script>

<template>
  <div class="editor-pane">
    <div class="toolbar">
      <button v-if="!editing" @click="startEdit">编辑</button>
      <template v-else>
        <button @click="save">保存</button>
        <button @click="editing = false">取消编辑</button>
      </template>
    </div>
    <textarea v-if="editing" v-model="draft" rows="24"></textarea>
    <MarkdownView v-else-if="markdown" :content="content" />
    <pre v-else class="plain">{{ content }}</pre>
  </div>
</template>
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd frontend && npm test`
Expected: 全部通过

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components frontend/tests/components.test.js
git commit -m "feat: Markdown 渲染与查看编辑组件"
```

---

### Task 5: 项目列表页 ProjectList

**Files:**
- Modify: `frontend/src/views/ProjectList.vue`（替换 Task 1 占位内容）
- Test: `frontend/tests/project-list.test.js`

**Interfaces:**
- Consumes: `api.listProjects()`、`api.createProject(name, videoDir)`
- Produces: 路由 `/` 页面；列表项链接到 `/projects/{id}`

- [ ] **Step 1: 写失败测试 frontend/tests/project-list.test.js**

```js
import { flushPromises, mount } from '@vue/test-utils'
import { expect, test, vi } from 'vitest'
import * as api from '../src/api'
import ProjectList from '../src/views/ProjectList.vue'

vi.mock('../src/api')

const stubs = { RouterLink: { template: '<a><slot /></a>' } }

test('加载并展示项目列表', async () => {
  api.listProjects.mockResolvedValue([
    { id: 'deadbeef', name: '霸总剧', episodes: [{}, {}] },
  ])
  const wrapper = mount(ProjectList, { global: { stubs } })
  await flushPromises()
  expect(wrapper.text()).toContain('霸总剧')
  expect(wrapper.text()).toContain('2 集')
})

test('创建项目后刷新列表', async () => {
  api.listProjects.mockResolvedValue([])
  api.createProject.mockResolvedValue({ id: 'deadbeef' })
  const wrapper = mount(ProjectList, { global: { stubs } })
  await flushPromises()
  await wrapper.findAll('input')[0].setValue('新剧')
  await wrapper.findAll('input')[1].setValue('D:/videos')
  await wrapper.find('form').trigger('submit')
  await flushPromises()
  expect(api.createProject).toHaveBeenCalledWith('新剧', 'D:/videos')
  expect(api.listProjects).toHaveBeenCalledTimes(2)
})

test('创建失败展示错误', async () => {
  api.listProjects.mockResolvedValue([])
  api.createProject.mockRejectedValue(new Error('目录不存在'))
  const wrapper = mount(ProjectList, { global: { stubs } })
  await flushPromises()
  await wrapper.findAll('input')[0].setValue('新剧')
  await wrapper.findAll('input')[1].setValue('Z:/nope')
  await wrapper.find('form').trigger('submit')
  await flushPromises()
  expect(wrapper.find('.error').text()).toContain('目录不存在')
})
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd frontend && npm test`
Expected: FAIL（占位视图无列表/表单）

- [ ] **Step 3: 实现 frontend/src/views/ProjectList.vue（整文件替换）**

```vue
<script setup>
import { onMounted, ref } from 'vue'
import * as api from '../api'

const projects = ref([])
const name = ref('')
const videoDir = ref('')
const error = ref('')

async function load() {
  projects.value = await api.listProjects()
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
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd frontend && npm test`
Expected: 全部通过

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/ProjectList.vue frontend/tests/project-list.test.js
git commit -m "feat: 项目列表与新建项目"
```

---

### Task 6: 项目详情壳 ProjectDetail（页签 + SSE 刷新）

**Files:**
- Modify: `frontend/src/views/ProjectDetail.vue`（替换 Task 1 占位内容）
- Create: `frontend/src/tabs/Stage1Extract.vue`、`frontend/src/tabs/ArtifactTab.vue`、`frontend/src/tabs/Stage3Settings.vue`、`frontend/src/tabs/Stage5Scripts.vue`（本任务先建占位，Task 7~9 分别实现）
- Test: `frontend/tests/project-detail.test.js`

**Interfaces:**
- Consumes: `api.getProject(pid)`、`sse.subscribeEvents(pid, onEvent)`
- Produces（Task 7~9 依赖，props 名称与类型必须一致）:
  - `provide('refresh', refresh)`：async 函数，重新拉取项目并更新 `project`
  - `Stage1Extract` props: `{pid: String, project: Object}`
  - `ArtifactTab` props: `{pid: String, kind: String, generateLabel: String}`（②用 `kind="analysis"`，④用 `kind="outline"`）
  - `Stage3Settings` props: `{pid: String}`
  - `Stage5Scripts` props: `{pid: String, project: Object}`

- [ ] **Step 1: 写失败测试 frontend/tests/project-detail.test.js**

```js
import { flushPromises, shallowMount } from '@vue/test-utils'
import { expect, test, vi } from 'vitest'
import * as api from '../src/api'
import * as sse from '../src/sse'
import ProjectDetail from '../src/views/ProjectDetail.vue'

vi.mock('../src/api')
vi.mock('../src/sse')

const project = {
  id: 'deadbeef', name: '霸总剧', video_dir: 'D:/v', running: false, episodes: [],
}

test('加载项目并渲染五个页签', async () => {
  api.getProject.mockResolvedValue(project)
  sse.subscribeEvents.mockReturnValue(vi.fn())
  const wrapper = shallowMount(ProjectDetail, { props: { pid: 'deadbeef' } })
  await flushPromises()
  expect(wrapper.text()).toContain('霸总剧')
  expect(wrapper.findAll('.tabs button').map((b) => b.text())).toEqual([
    '① 扒剧', '② 拆解报告', '③ 新剧设定', '④ 大纲', '⑤ 新剧剧本',
  ])
})

test('SSE 事件触发刷新，卸载时取消订阅', async () => {
  api.getProject.mockResolvedValue(project)
  let handler
  const stop = vi.fn()
  sse.subscribeEvents.mockImplementation((pid, cb) => {
    handler = cb
    return stop
  })
  const wrapper = shallowMount(ProjectDetail, { props: { pid: 'deadbeef' } })
  await flushPromises()
  expect(api.getProject).toHaveBeenCalledTimes(1)
  await handler({ type: 'item_done', item: 1, ok: true })
  expect(api.getProject).toHaveBeenCalledTimes(2)
  wrapper.unmount()
  expect(stop).toHaveBeenCalled()
})

test('切换页签渲染对应组件', async () => {
  api.getProject.mockResolvedValue(project)
  sse.subscribeEvents.mockReturnValue(vi.fn())
  const wrapper = shallowMount(ProjectDetail, { props: { pid: 'deadbeef' } })
  await flushPromises()
  expect(wrapper.findComponent({ name: 'Stage1Extract' }).exists()).toBe(true)
  await wrapper.findAll('.tabs button')[1].trigger('click')
  expect(wrapper.findComponent({ name: 'ArtifactTab' }).exists()).toBe(true)
})
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd frontend && npm test`
Expected: FAIL（占位视图无页签）

- [ ] **Step 3: 创建四个占位页签组件**

`src/tabs/Stage1Extract.vue`:

```vue
<script>
export default { name: 'Stage1Extract' }
</script>
<script setup>
defineProps({ pid: { type: String, required: true }, project: { type: Object, required: true } })
</script>
<template>
  <div>① 扒剧（待实现）</div>
</template>
```

`src/tabs/ArtifactTab.vue`:

```vue
<script>
export default { name: 'ArtifactTab' }
</script>
<script setup>
defineProps({
  pid: { type: String, required: true },
  kind: { type: String, required: true },
  generateLabel: { type: String, required: true },
})
</script>
<template>
  <div>产物页签（待实现）</div>
</template>
```

`src/tabs/Stage3Settings.vue`:

```vue
<script>
export default { name: 'Stage3Settings' }
</script>
<script setup>
defineProps({ pid: { type: String, required: true } })
</script>
<template>
  <div>③ 新剧设定（待实现）</div>
</template>
```

`src/tabs/Stage5Scripts.vue`:

```vue
<script>
export default { name: 'Stage5Scripts' }
</script>
<script setup>
defineProps({ pid: { type: String, required: true }, project: { type: Object, required: true } })
</script>
<template>
  <div>⑤ 新剧剧本（待实现）</div>
</template>
```

（`export default { name: … }` 与 `<script setup>` 并存是 Vue 官方支持的写法，用于给 shallowMount 的 `findComponent({ name })` 提供组件名。Task 7~9 重写这些文件时必须保留双 script 结构。）

- [ ] **Step 4: 实现 frontend/src/views/ProjectDetail.vue（整文件替换）**

```vue
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
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd frontend && npm test`
Expected: 全部通过

- [ ] **Step 6: Commit**

```bash
git add frontend/src/views/ProjectDetail.vue frontend/src/tabs frontend/tests/project-detail.test.js
git commit -m "feat: 项目详情页签壳与 SSE 刷新"
```

---

### Task 7: 页签① Stage1Extract（扒剧）

**Files:**
- Modify: `frontend/src/tabs/Stage1Extract.vue`（整文件替换 Task 6 占位）
- Test: `frontend/tests/stage1.test.js`

**Interfaces:**
- Consumes: `api.stage1Start(pid, episodes?)`、`api.stage1Cancel(pid)`、`api.updateMapping(pid, episodes)`、`api.getEpisodeScript(pid, ep)`、`api.putEpisodeScript(pid, ep, content)`、`api.exportUrl(pid, 'original')`、`inject('refresh')`、`EditorPane`
- Produces: 页签①完整交互（分集状态表、开始/取消、失败重跑、集数映射编辑、单集查看/编辑、导出原剧汇总）

- [ ] **Step 1: 写失败测试 frontend/tests/stage1.test.js**

```js
import { flushPromises, mount } from '@vue/test-utils'
import { expect, test, vi } from 'vitest'
import * as api from '../src/api'
import Stage1Extract from '../src/tabs/Stage1Extract.vue'

vi.mock('../src/api')

function makeProject(running = false) {
  return {
    id: 'deadbeef', name: '霸总剧', video_dir: 'D:/v', running,
    episodes: [
      { episode: 1, file: '第01集.mp4', status: 'done', error: '' },
      { episode: 2, file: '第02集.mp4', status: 'failed', error: '上传超时' },
      { episode: 3, file: '第03集.mp4', status: 'pending', error: '' },
    ],
  }
}

function opts(project) {
  return {
    props: { pid: 'deadbeef', project },
    global: { provide: { refresh: vi.fn() } },
  }
}

function button(wrapper, text) {
  return wrapper.findAll('button').find((b) => b.text() === text)
}

test('展示分集状态、错误与完成计数', () => {
  api.exportUrl.mockReturnValue('#')
  const wrapper = mount(Stage1Extract, opts(makeProject()))
  expect(wrapper.text()).toContain('完成 1 / 3')
  expect(wrapper.text()).toContain('第02集.mp4')
  expect(wrapper.text()).toContain('上传超时')
  expect(wrapper.find('.status-done').exists()).toBe(true)
})

test('开始扒剧与失败重跑', async () => {
  api.exportUrl.mockReturnValue('#')
  api.stage1Start.mockResolvedValue({ started: [] })
  const wrapper = mount(Stage1Extract, opts(makeProject()))
  await button(wrapper, '开始扒剧').trigger('click')
  await flushPromises()
  expect(api.stage1Start).toHaveBeenCalledWith('deadbeef')
  await button(wrapper, '重跑').trigger('click')
  await flushPromises()
  expect(api.stage1Start).toHaveBeenCalledWith('deadbeef', [2])
})

test('运行中显示取消按钮', async () => {
  api.exportUrl.mockReturnValue('#')
  api.stage1Cancel.mockResolvedValue({ ok: true })
  const wrapper = mount(Stage1Extract, opts(makeProject(true)))
  expect(button(wrapper, '开始扒剧')).toBeUndefined()
  await button(wrapper, '取消').trigger('click')
  await flushPromises()
  expect(api.stage1Cancel).toHaveBeenCalledWith('deadbeef')
})

test('编辑并保存集数映射', async () => {
  api.exportUrl.mockReturnValue('#')
  api.updateMapping.mockResolvedValue({ ok: true })
  const wrapper = mount(Stage1Extract, opts(makeProject()))
  await button(wrapper, '调整集数对应').trigger('click')
  await wrapper.findAll('td input')[0].setValue(9)
  await button(wrapper, '保存集数对应').trigger('click')
  await flushPromises()
  expect(api.updateMapping).toHaveBeenCalledWith('deadbeef', [
    { episode: 9, file: '第01集.mp4' },
    { episode: 2, file: '第02集.mp4' },
    { episode: 3, file: '第03集.mp4' },
  ])
})

test('查看并保存单集剧本', async () => {
  api.exportUrl.mockReturnValue('#')
  api.getEpisodeScript.mockResolvedValue({ content: '1-1 日 内 客厅' })
  api.putEpisodeScript.mockResolvedValue({ ok: true })
  const wrapper = mount(Stage1Extract, opts(makeProject()))
  await button(wrapper, '查看/编辑').trigger('click')
  await flushPromises()
  expect(api.getEpisodeScript).toHaveBeenCalledWith('deadbeef', 1)
  expect(wrapper.text()).toContain('第 1 集原剧剧本')
  expect(wrapper.text()).toContain('1-1 日 内 客厅')
  await button(wrapper, '编辑').trigger('click')
  await wrapper.find('.editor-pane textarea').setValue('1-1 夜 外 天台')
  await button(wrapper, '保存').trigger('click')
  await flushPromises()
  expect(api.putEpisodeScript).toHaveBeenCalledWith('deadbeef', 1, '1-1 夜 外 天台')
})
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd frontend && npm test`
Expected: FAIL（占位组件无交互）

- [ ] **Step 3: 实现 frontend/src/tabs/Stage1Extract.vue（整文件替换）**

```vue
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
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd frontend && npm test`
Expected: 全部通过

- [ ] **Step 5: Commit**

```bash
git add frontend/src/tabs/Stage1Extract.vue frontend/tests/stage1.test.js
git commit -m "feat: 扒剧页签"
```

---

### Task 8: 页签②④ ArtifactTab 与 页签③ Stage3Settings

**Files:**
- Modify: `frontend/src/tabs/ArtifactTab.vue`、`frontend/src/tabs/Stage3Settings.vue`（整文件替换 Task 6 占位）
- Test: `frontend/tests/artifact-stage3.test.js`

**Interfaces:**
- Consumes: `api.getArtifact/putArtifact`、`api.stage2Generate`、`api.stage4Generate`、`api.stage3Suggest`、`api.stage3Refine`、`EditorPane`、`MarkdownView`
- Produces:
  - `ArtifactTab`（props 同 Task 6）：`kind="analysis"` 时生成按钮调 `stage2Generate`，`kind="outline"` 时调 `stage4Generate`；加载已有产物、生成、查看/编辑/保存
  - `Stage3Settings`：AI 建议题材（结果仅展示不落盘）、自由草稿 + 「AI 完善设定」（落盘 settings）、已有设定查看/编辑/保存

- [ ] **Step 1: 写失败测试 frontend/tests/artifact-stage3.test.js**

```js
import { flushPromises, mount } from '@vue/test-utils'
import { expect, test, vi } from 'vitest'
import * as api from '../src/api'
import ArtifactTab from '../src/tabs/ArtifactTab.vue'
import Stage3Settings from '../src/tabs/Stage3Settings.vue'

vi.mock('../src/api')

function button(wrapper, text) {
  return wrapper.findAll('button').find((b) => b.text() === text)
}

test('ArtifactTab 加载已有产物', async () => {
  api.getArtifact.mockResolvedValue({ content: '# 已有报告' })
  const wrapper = mount(ArtifactTab, {
    props: { pid: 'deadbeef', kind: 'analysis', generateLabel: '生成拆解报告' },
  })
  await flushPromises()
  expect(api.getArtifact).toHaveBeenCalledWith('deadbeef', 'analysis')
  expect(wrapper.text()).toContain('已有报告')
})

test('ArtifactTab kind=analysis 生成调 stage2Generate 并可编辑保存', async () => {
  api.getArtifact.mockRejectedValue(new Error('尚未生成'))
  api.stage2Generate.mockResolvedValue({ content: '# 报告' })
  api.putArtifact.mockResolvedValue({ ok: true })
  const wrapper = mount(ArtifactTab, {
    props: { pid: 'deadbeef', kind: 'analysis', generateLabel: '生成拆解报告' },
  })
  await flushPromises()
  expect(wrapper.text()).toContain('尚未生成')
  await button(wrapper, '生成拆解报告').trigger('click')
  await flushPromises()
  expect(api.stage2Generate).toHaveBeenCalledWith('deadbeef')
  expect(wrapper.text()).toContain('报告')
  await button(wrapper, '编辑').trigger('click')
  await wrapper.find('textarea').setValue('# 修改后')
  await button(wrapper, '保存').trigger('click')
  await flushPromises()
  expect(api.putArtifact).toHaveBeenCalledWith('deadbeef', 'analysis', '# 修改后')
})

test('ArtifactTab kind=outline 生成调 stage4Generate', async () => {
  api.getArtifact.mockRejectedValue(new Error('尚未生成'))
  api.stage4Generate.mockResolvedValue({ content: '# 大纲' })
  const wrapper = mount(ArtifactTab, {
    props: { pid: 'deadbeef', kind: 'outline', generateLabel: '生成逐集大纲' },
  })
  await flushPromises()
  await button(wrapper, '生成逐集大纲').trigger('click')
  await flushPromises()
  expect(api.stage4Generate).toHaveBeenCalledWith('deadbeef')
  expect(wrapper.text()).toContain('大纲')
})

test('ArtifactTab 生成失败展示错误', async () => {
  api.getArtifact.mockRejectedValue(new Error('尚未生成'))
  api.stage2Generate.mockRejectedValue(new Error('还没有已完成的扒剧剧本'))
  const wrapper = mount(ArtifactTab, {
    props: { pid: 'deadbeef', kind: 'analysis', generateLabel: '生成拆解报告' },
  })
  await flushPromises()
  await button(wrapper, '生成拆解报告').trigger('click')
  await flushPromises()
  expect(wrapper.find('.error').text()).toContain('还没有已完成的扒剧剧本')
})

test('Stage3 AI 建议题材仅展示', async () => {
  api.getArtifact.mockRejectedValue(new Error('尚未生成'))
  api.stage3Suggest.mockResolvedValue({ content: '1. 都市修仙\n2. 民国悬疑' })
  const wrapper = mount(Stage3Settings, { props: { pid: 'deadbeef' } })
  await flushPromises()
  await button(wrapper, 'AI 建议新题材').trigger('click')
  await flushPromises()
  expect(api.stage3Suggest).toHaveBeenCalledWith('deadbeef')
  expect(wrapper.text()).toContain('都市修仙')
  expect(api.putArtifact).not.toHaveBeenCalled()
})

test('Stage3 AI 完善设定并可编辑保存', async () => {
  api.getArtifact.mockRejectedValue(new Error('尚未生成'))
  api.stage3Refine.mockResolvedValue({ content: '# 新剧设定' })
  api.putArtifact.mockResolvedValue({ ok: true })
  const wrapper = mount(Stage3Settings, { props: { pid: 'deadbeef' } })
  await flushPromises()
  await wrapper.find('textarea').setValue('题材：都市修仙')
  await button(wrapper, 'AI 完善设定').trigger('click')
  await flushPromises()
  expect(api.stage3Refine).toHaveBeenCalledWith('deadbeef', '题材：都市修仙')
  expect(wrapper.text()).toContain('新剧设定')
  await button(wrapper, '编辑').trigger('click')
  await wrapper.find('.editor-pane textarea').setValue('# 改过的设定')
  await button(wrapper, '保存').trigger('click')
  await flushPromises()
  expect(api.putArtifact).toHaveBeenCalledWith('deadbeef', 'settings', '# 改过的设定')
})
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd frontend && npm test`
Expected: FAIL（占位组件无交互）

- [ ] **Step 3: 实现 frontend/src/tabs/ArtifactTab.vue（整文件替换）**

```vue
<script>
export default { name: 'ArtifactTab' }
</script>
<script setup>
import { onMounted, ref } from 'vue'
import * as api from '../api'
import EditorPane from '../components/EditorPane.vue'

const props = defineProps({
  pid: { type: String, required: true },
  kind: { type: String, required: true },
  generateLabel: { type: String, required: true },
})

const generators = { analysis: api.stage2Generate, outline: api.stage4Generate }

const content = ref('')
const busy = ref(false)
const error = ref('')

async function load() {
  try {
    content.value = (await api.getArtifact(props.pid, props.kind)).content
  } catch {
    content.value = ''
  }
}

async function generate() {
  busy.value = true
  error.value = ''
  try {
    content.value = (await generators[props.kind](props.pid)).content
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

async function save(text) {
  try {
    await api.putArtifact(props.pid, props.kind, text)
    content.value = text
  } catch (e) {
    error.value = e.message
  }
}

onMounted(load)
</script>

<template>
  <div>
    <button :disabled="busy" @click="generate">{{ busy ? '生成中…' : generateLabel }}</button>
    <p v-if="error" class="error">{{ error }}</p>
    <EditorPane v-if="content" :content="content" @save="save" />
    <p v-else class="muted">尚未生成</p>
  </div>
</template>
```

- [ ] **Step 4: 实现 frontend/src/tabs/Stage3Settings.vue（整文件替换）**

```vue
<script>
export default { name: 'Stage3Settings' }
</script>
<script setup>
import { onMounted, ref } from 'vue'
import * as api from '../api'
import EditorPane from '../components/EditorPane.vue'
import MarkdownView from '../components/MarkdownView.vue'

const props = defineProps({ pid: { type: String, required: true } })

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
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd frontend && npm test`
Expected: 全部通过

- [ ] **Step 6: Commit**

```bash
git add frontend/src/tabs/ArtifactTab.vue frontend/src/tabs/Stage3Settings.vue frontend/tests/artifact-stage3.test.js
git commit -m "feat: 拆解报告、大纲与新剧设定页签"
```

---

### Task 9: 页签⑤ Stage5Scripts（新剧剧本）

**Files:**
- Modify: `frontend/src/tabs/Stage5Scripts.vue`（整文件替换 Task 6 占位）
- Test: `frontend/tests/stage5.test.js`

**Interfaces:**
- Consumes: `api.stage5Start(pid, episodes?, extra?)`、`api.stage5Generate(pid, episode, extra?)`、`api.stage1Cancel(pid)`（后端取消端点对任何批次生效）、`api.getNewScript/putNewScript`、`api.exportUrl(pid, 'new')`、`inject('refresh')`、`EditorPane`
- Produces: 页签⑤完整交互（批量生成 + 附加指令、单集生成/重生成、查看/编辑、导出新剧汇总）

- [ ] **Step 1: 写失败测试 frontend/tests/stage5.test.js**

```js
import { flushPromises, mount } from '@vue/test-utils'
import { expect, test, vi } from 'vitest'
import * as api from '../src/api'
import Stage5Scripts from '../src/tabs/Stage5Scripts.vue'

vi.mock('../src/api')

function makeProject(running = false) {
  return {
    id: 'deadbeef', name: '霸总剧', video_dir: 'D:/v', running,
    episodes: [
      { episode: 1, file: '第01集.mp4', status: 'done', error: '' },
      { episode: 2, file: '第02集.mp4', status: 'done', error: '' },
    ],
  }
}

function opts(project) {
  return {
    props: { pid: 'deadbeef', project },
    global: { provide: { refresh: vi.fn() } },
  }
}

function button(wrapper, text) {
  return wrapper.findAll('button').find((b) => b.text() === text)
}

test('批量生成带附加指令', async () => {
  api.exportUrl.mockReturnValue('#')
  api.stage5Start.mockResolvedValue({ started: [1, 2] })
  const wrapper = mount(Stage5Scripts, opts(makeProject()))
  await wrapper.find('textarea').setValue('台词更口语化')
  await button(wrapper, '批量生成全部').trigger('click')
  await flushPromises()
  expect(api.stage5Start).toHaveBeenCalledWith('deadbeef', null, '台词更口语化')
})

test('运行中禁用生成并可取消', async () => {
  api.exportUrl.mockReturnValue('#')
  api.stage1Cancel.mockResolvedValue({ ok: true })
  const wrapper = mount(Stage5Scripts, opts(makeProject(true)))
  expect(button(wrapper, '批量生成全部').attributes('disabled')).toBeDefined()
  await button(wrapper, '取消').trigger('click')
  await flushPromises()
  expect(api.stage1Cancel).toHaveBeenCalledWith('deadbeef')
})

test('单集生成并展示结果', async () => {
  api.exportUrl.mockReturnValue('#')
  api.stage5Generate.mockResolvedValue({ content: '1-1 夜 内 修炼室' })
  const wrapper = mount(Stage5Scripts, opts(makeProject()))
  await wrapper.find('textarea').setValue('更热血')
  await wrapper.findAll('button').filter((b) => b.text() === '生成/重生成')[1].trigger('click')
  await flushPromises()
  expect(api.stage5Generate).toHaveBeenCalledWith('deadbeef', 2, '更热血')
  expect(wrapper.text()).toContain('新剧第 2 集')
  expect(wrapper.text()).toContain('1-1 夜 内 修炼室')
})

test('查看并保存已有新剧本', async () => {
  api.exportUrl.mockReturnValue('#')
  api.getNewScript.mockResolvedValue({ content: '旧内容' })
  api.putNewScript.mockResolvedValue({ ok: true })
  const wrapper = mount(Stage5Scripts, opts(makeProject()))
  await wrapper.findAll('button').filter((b) => b.text() === '查看')[0].trigger('click')
  await flushPromises()
  expect(api.getNewScript).toHaveBeenCalledWith('deadbeef', 1)
  await button(wrapper, '编辑').trigger('click')
  await wrapper.find('.editor-pane textarea').setValue('改后内容')
  await button(wrapper, '保存').trigger('click')
  await flushPromises()
  expect(api.putNewScript).toHaveBeenCalledWith('deadbeef', 1, '改后内容')
})

test('查看不存在的新剧本展示错误', async () => {
  api.exportUrl.mockReturnValue('#')
  api.getNewScript.mockRejectedValue(new Error('该集新剧本不存在'))
  const wrapper = mount(Stage5Scripts, opts(makeProject()))
  await wrapper.findAll('button').filter((b) => b.text() === '查看')[0].trigger('click')
  await flushPromises()
  expect(wrapper.find('.error').text()).toContain('该集新剧本不存在')
})
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd frontend && npm test`
Expected: FAIL（占位组件无交互）

- [ ] **Step 3: 实现 frontend/src/tabs/Stage5Scripts.vue（整文件替换）**

```vue
<script>
export default { name: 'Stage5Scripts' }
</script>
<script setup>
import { inject, ref } from 'vue'
import * as api from '../api'
import EditorPane from '../components/EditorPane.vue'

const props = defineProps({
  pid: { type: String, required: true },
  project: { type: Object, required: true },
})
const refresh = inject('refresh')

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
        <tr><th>集</th><th>操作</th></tr>
      </thead>
      <tbody>
        <tr v-for="e in project.episodes" :key="e.episode">
          <td>第 {{ e.episode }} 集</td>
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
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd frontend && npm test`
Expected: 全部通过

- [ ] **Step 5: Commit**

```bash
git add frontend/src/tabs/Stage5Scripts.vue frontend/tests/stage5.test.js
git commit -m "feat: 新剧剧本页签"
```

---

### Task 10: 构建验证与前端 README

**Files:**
- Create: `frontend/README.md`

**Interfaces:**
- Consumes: 全部前序任务

- [ ] **Step 1: 全量测试与构建验证**

Run: `cd frontend && npm test && npm run build`
Expected: 测试全部通过；`vite build` 成功生成 `frontend/dist/`

- [ ] **Step 2: 创建 frontend/README.md（内容一字不差）**

````markdown
# 短剧扒剧与仿写 — 前端

Vue 3 + Vite 单页应用，对接 `backend/` 的 FastAPI 服务。

## 安装

需要 Node.js ≥ 18。

```bash
cd frontend
npm install
```

## 开发运行

先启动后端（另开终端）：

```bash
cd backend
python -m app.main
```

再启动前端开发服务器（`/api` 自动代理到 `http://127.0.0.1:8000`）：

```bash
cd frontend
npm run dev
```

浏览器打开终端提示的地址（默认 http://localhost:5173）。

## 使用流程

1. 首页新建项目：填项目名称与视频文件夹路径，后端自动扫描分集
2. 页签①：开始扒剧（可取消/单集重跑/调整集数对应），完成后可查看编辑每集剧本、导出原剧汇总
3. 页签②：生成全剧拆解报告，可编辑
4. 页签③：AI 建议新题材 → 写设定草稿 → AI 完善设定，可编辑
5. 页签④：生成逐集大纲，可编辑
6. 页签⑤：批量或单集生成新剧剧本（支持附加指令），可编辑、导出新剧汇总

## 测试与构建

```bash
npm test        # vitest（jsdom）
npm run build   # 产物在 dist/
```
````

- [ ] **Step 3: 手工冒烟（需要用户配合，不阻塞提交）**

后端配好真实 API key 后：`npm run dev` 打开首页 → 新建项目 → 页签①对单集视频跑通扒剧并在界面看到状态流转。此步骤记录在报告中即可。

- [ ] **Step 4: Commit**

```bash
git add frontend/README.md
git commit -m "docs: 前端 README 与使用说明"
```

