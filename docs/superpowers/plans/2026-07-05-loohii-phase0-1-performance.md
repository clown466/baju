# 鹿绘 AI 阶段 0+1：准备 + 性能快赢 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 打通本地开发链路，并消除画布卡顿三大元凶（节点全量重渲染、5 秒轮询无条件 setState、图片原图直出无懒加载），逐项部署上线。

**Architecture:** 纯前端低风险改动：xyflow 自定义节点在 `nodeTypes` 注册处统一 `memo` 包裹；轮询结果用指纹比较避免无效 setState；`<img>` 补懒加载；Dashboard 预取画布 chunk。不改任何 API、不改数据库。

**Tech Stack:** React 18.3 + Vite 6 + @xyflow/react 12 + zustand；测试用 node:test（`npx tsx --test`）；部署为 Docker 镜像 + nginx 反代。

**规格文档:** `docs/superpowers/specs/2026-07-05-loohii-frontend-optimization-design.md`

## Global Constraints

- 仓库：https://github.com/clown466/loohii ，分支 `main`；本地克隆位于 `H:\claude项目\loohii`
- 生产服务器：`root@157.254.234.105`，项目目录 `/projects/loohii`，容器 `loohii-app`（127.0.0.1:3001）
- 服务器连接命令前缀（下文简称 `PLINK`）：
  `plink -ssh -batch -hostkey "SHA256:oMogBHYLu9S5widJ1D2MopEELwkNTb0EPS7OYnIzbJI" root@157.254.234.105 -pw "<密码>"`
- 本阶段**禁止**：改 API 行为、改 Prisma 模型、改 nginx（那是阶段 2）、引入新 npm 依赖
- 每个任务完成即 commit；部署仅在 Task 7 统一进行
- 所有前端验证命令在 `H:\claude项目\loohii` 下执行；`npm run build` 必须通过才能 commit

---

### Task 1: 服务器未提交改动入库 + 本地同步

服务器 `/projects/loohii` 有未提交改动（`server/src/routes/agent.ts`、`server/src/routes/characters.ts`、`server/src/routes/workflows.ts`、`server/src/routes/workflows.test.ts`、`src/app/features/canvas/canvasHelpers.ts`，可能还有未跟踪的新文件如 `src/app/features/canvas/canvasNodeChanges.test.ts`），必须先入库，否则本地开发会与线上代码分叉。

**Files:**
- 无本地文件改动；操作对象是服务器仓库与本地克隆的 git 状态

**Interfaces:**
- Produces: 本地 `H:\claude项目\loohii` 与 origin/main 同步且包含服务器全部工作成果

- [ ] **Step 1: 查看服务器完整 git 状态（含未跟踪文件）**

Run:
```bash
PLINK "cd /projects/loohii && git status --short && git diff --stat"
```
Expected: 列出 M 开头的已修改文件和 ?? 开头的未跟踪文件。记下清单。

- [ ] **Step 2: 服务器上提交并推送**

```bash
PLINK "cd /projects/loohii && git add -A && git commit -m 'chore: commit in-progress server-side work before local development' && git push origin main"
```
Expected: 输出 `main -> main`，push 成功。若 push 要求凭据失败，改用：先 `git format-patch origin/main --stdout > /tmp/wip.patch`，本地 `pscp` 拉回后 `git am`，再由本地推送。

- [ ] **Step 3: 本地同步**

```bash
cd "H:\claude项目\loohii" && git pull origin main && git log --oneline -3
```
Expected: 最新 commit 为 Step 2 的提交；`git status` 干净。

- [ ] **Step 4: 确认服务器与本地指向同一 commit**

```bash
PLINK "cd /projects/loohii && git rev-parse HEAD" && cd "H:\claude项目\loohii" && git rev-parse HEAD
```
Expected: 两个 SHA 相同。

---

### Task 2: 本地开发环境跑通

**Files:**
- Create: `H:\claude项目\loohii\.env`（从服务器复制，不入库——确认已在 `.gitignore`）

**Interfaces:**
- Produces: 本地 `http://localhost:5173`（vite dev）+ `http://localhost:3001`（API）可登录、可打开画布

- [ ] **Step 1: 安装依赖**

```bash
cd "H:\claude项目\loohii" && npm install
```
Expected: 无 error 退出（warning 可忽略）。

- [ ] **Step 2: 配置 vite 代理指向生产 API（本机虚拟化禁用，无法跑 Docker；阶段 0+1 全部改动为纯前端，无需本地数据库）**

创建 `H:\claude项目\loohii\.env.local`（vite 专用，确认在 `.gitignore` 内，不入库）：

```
VITE_DEV_API_PROXY=https://loohii.com
```
`vite.config.ts` 已内置该变量的 proxy 逻辑（`/api` 与 `/socket.io` 转发 + `changeOrigin`），无需改代码。**注意：本地 dev 的读写会作用于生产数据，冒烟时只用自己的账号做只读浏览。**

- [ ] **Step 3: 构建验证**

```bash
cd "H:\claude项目\loohii" && npm run build
```
Expected: vite build 成功，作为后续任务的编译基线。

- [ ] **Step 4: （跳过）本地数据库初始化**

本机无虚拟化，跳过 docker compose 与 prisma migrate。服务端改动的阶段（2/3/4）将直接以生产镜像构建+服务器验证的方式进行，届时在计划中单独安排。

- [ ] **Step 5: 启动前端 dev 并冒烟**

```bash
cd "H:\claude项目\loohii" && npm run dev
```
浏览器打开 `http://localhost:5173`：用现有账号登录（请求经代理达生产 API）→ 打开一个项目画布。
Expected: 页面正常渲染、能加载真实项目数据，无控制台报错。

- [ ] **Step 6: 基线记录（供 Task 3 对比）**

React DevTools → Profiler → 录制 → 在画布上添加 2 个节点后拖动其中一个 → 停止录制。
Expected: 观察到拖动时**所有**节点组件都出现在火焰图中（这是待修复的基线行为）。截图存档。

---

### Task 3: 画布节点 memo 化

xyflow 要求自定义节点用 `memo` 包裹，否则任何画布交互都触发全部节点重渲染。在 `nodeTypes` 注册处统一包裹（单文件改动，覆盖全部 15 个注册项）。

**Files:**
- Modify: `loohii/src/app/features/canvas/nodes/index.ts:27-43`

**Interfaces:**
- Consumes: 各节点组件现有导出（如 `export const SceneNode = ({ id, data, selected }: CanvasNodeProps) => {...}`）
- Produces: `nodeTypes` 对象，键名与值语义完全不变（`ProjectCanvasPage.tsx:62` 的 import 无需改动）

- [ ] **Step 1: 修改 nodeTypes 为 memo 包裹**

将 `src/app/features/canvas/nodes/index.ts` 中的 `nodeTypes` 定义（第 27-43 行）替换为：

```ts
import { memo } from 'react';

export const nodeTypes = {
  scene: memo(SceneNode),
  character: memo(CharacterNode),
  episode: memo(WorkflowNode),
  asset: memo(WorkflowNode),
  workflow: memo(WorkflowNode),
  directorBoard: memo(WorkflowNode),
  imageInput: memo(ImageInputNode),
  generation: memo(GenerationNode),
  video: memo(VideoNode),
  audio: memo(AudioInputNode),
  translation: memo(TranslationNode),
  promptOptimizer: memo(PromptOptimizerNode),
  promptInspector: memo(PromptInspectorNode),
  agent: memo(AgentNode),
  section: memo(SectionNode),
};
```
（`import { memo } from 'react';` 放到文件顶部 import 区。文件顶部的 12 行 `export { ... }` 再导出保持不动。）

- [ ] **Step 2: 构建验证**

```bash
cd "H:\claude项目\loohii" && npm run build
```
Expected: 构建成功，无 TS/编译错误。

- [ ] **Step 3: 行为回归（对照 Task 2 Step 6 基线）**

本地 dev 环境，Profiler 录制同样操作：拖动 2 个节点之一。
Expected: 火焰图中**只有被拖动的节点**重渲染。再逐项验证：点选节点（选中态边框出现）、编辑节点文本、节点内按钮可点击——行为与改动前一致。

- [ ] **Step 4: 检查 memo 失效点**

在 `ProjectCanvasPage.tsx:5405` 附近确认 `nodeTypes={nodeTypes}` 传入的是模块级常量（是——import 自 index.ts），而非组件内新建对象。无需改动，仅确认。
Expected: `nodeTypes` 引用稳定。

- [ ] **Step 5: Commit**

```bash
cd "H:\claude项目\loohii" && git add src/app/features/canvas/nodes/index.ts && git commit -m "perf(canvas): memoize custom node components in nodeTypes registry"
```

---

### Task 4: 轮询指纹比较 + 失败保留旧数据（TDD）

5 秒轮询即使数据未变也 `setGenerationRecords(新数组)`，触发 6768 行页面重渲染；网络抖动时 catch 清空列表导致闪空。抽出纯函数做指纹比较。

**Files:**
- Create: `loohii/src/app/features/canvas/generationRecordsFingerprint.ts`
- Create: `loohii/src/app/features/canvas/generationRecordsFingerprint.test.ts`
- Modify: `loohii/src/app/pages/ProjectCanvasPage.tsx:1088-1118`（`useEffect` 轮询块）

**Interfaces:**
- Produces: `generationRecordsFingerprint(records: ReadonlyArray<{ id?: string; updatedAt?: string | null; status?: string | null }>): string`

- [ ] **Step 1: 写失败测试**

创建 `src/app/features/canvas/generationRecordsFingerprint.test.ts`：

```ts
import assert from "node:assert/strict";
import test from "node:test";
import { generationRecordsFingerprint } from "./generationRecordsFingerprint";

test("same records produce same fingerprint", () => {
  const a = [{ id: "r1", updatedAt: "2026-07-05T00:00:00Z", status: "succeeded" }];
  const b = [{ id: "r1", updatedAt: "2026-07-05T00:00:00Z", status: "succeeded" }];
  assert.equal(generationRecordsFingerprint(a), generationRecordsFingerprint(b));
});

test("changed updatedAt changes fingerprint", () => {
  const a = [{ id: "r1", updatedAt: "2026-07-05T00:00:00Z", status: "running" }];
  const b = [{ id: "r1", updatedAt: "2026-07-05T00:01:00Z", status: "running" }];
  assert.notEqual(generationRecordsFingerprint(a), generationRecordsFingerprint(b));
});

test("changed status changes fingerprint", () => {
  const a = [{ id: "r1", updatedAt: "2026-07-05T00:00:00Z", status: "running" }];
  const b = [{ id: "r1", updatedAt: "2026-07-05T00:00:00Z", status: "succeeded" }];
  assert.notEqual(generationRecordsFingerprint(a), generationRecordsFingerprint(b));
});

test("different order changes fingerprint (order matters for rendering)", () => {
  const r1 = { id: "r1", updatedAt: "t", status: "s" };
  const r2 = { id: "r2", updatedAt: "t", status: "s" };
  assert.notEqual(generationRecordsFingerprint([r1, r2]), generationRecordsFingerprint([r2, r1]));
});

test("missing fields are tolerated", () => {
  assert.equal(typeof generationRecordsFingerprint([{}]), "string");
  assert.equal(generationRecordsFingerprint([]), "");
});
```

- [ ] **Step 2: 运行确认失败**

```bash
cd "H:\claude项目\loohii" && npx tsx --test src/app/features/canvas/generationRecordsFingerprint.test.ts
```
Expected: FAIL（模块不存在）。

- [ ] **Step 3: 实现**

创建 `src/app/features/canvas/generationRecordsFingerprint.ts`：

```ts
export function generationRecordsFingerprint(
  records: ReadonlyArray<{ id?: string; updatedAt?: string | null; status?: string | null }>,
): string {
  return records
    .map((r) => `${r.id ?? ""}:${r.updatedAt ?? ""}:${r.status ?? ""}`)
    .join("|");
}
```

- [ ] **Step 4: 运行确认通过**

```bash
cd "H:\claude项目\loohii" && npx tsx --test src/app/features/canvas/generationRecordsFingerprint.test.ts
```
Expected: 5 项全部 PASS。

- [ ] **Step 5: 集成到轮询 effect**

`src/app/pages/ProjectCanvasPage.tsx`：
1）文件顶部 canvas 相关 import 区加入：
```ts
import { generationRecordsFingerprint } from '../features/canvas/generationRecordsFingerprint';
```
2）将轮询 `useEffect`（约 1088 行起）改为（仅 then/catch 部分变化，其余保持原样）：

```ts
  useEffect(() => {
    if (!projectId || projectId === 'local') {
      setGenerationRecords([]);
      return;
    }
    let cancelled = false;
    let lastFingerprint: string | null = null;
    const loadRecords = () => {
      apiClient.listGenerationRecords(projectId, { limit: 120, compact: true })
        .then((records) => {
          if (!cancelled) {
            const activeGenerationKeys = canvasActiveGenerationRecoveryKeys(useCanvasStore.getState().nodes);
            const filtered = records.filter((record) => (
              generationRecordBelongsToEpisode(record, activeEpisodeId, selectedEpisode) ||
              generationRecordMatchesActiveCanvasGeneration(record, activeGenerationKeys)
            ));
            const fingerprint = generationRecordsFingerprint(filtered);
            if (fingerprint !== lastFingerprint) {
              lastFingerprint = fingerprint;
              setGenerationRecords(filtered);
            }
          }
        })
        .catch(() => {
          // 网络抖动时保留旧数据，不清空列表
        });
    };
    loadRecords();
    const timer = window.setInterval(loadRecords, 5000);
    window.addEventListener(CANVAS_GENERATION_RECORDS_REFRESH_EVENT, loadRecords);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
      window.removeEventListener(CANVAS_GENERATION_RECORDS_REFRESH_EVENT, loadRecords);
    };
  }, [activeEpisodeId, projectId, selectedEpisode]);
```

- [ ] **Step 6: 构建 + 手动验证**

```bash
cd "H:\claude项目\loohii" && npm run build
```
本地 dev：打开画布页，React DevTools Profiler 录 20 秒（期间不操作）。
Expected: build 通过；Profiler 中 ProjectCanvasPage **零重渲染**（改动前每 5 秒一次）。DevTools Network 面板切 Offline 15 秒再恢复：记录列表不闪空。

- [ ] **Step 7: Commit**

```bash
cd "H:\claude项目\loohii" && git add src/app/features/canvas/generationRecordsFingerprint.ts src/app/features/canvas/generationRecordsFingerprint.test.ts src/app/pages/ProjectCanvasPage.tsx && git commit -m "perf(canvas): skip setState when generation records unchanged; keep data on fetch error"
```

---

### Task 5: 图片懒加载

30 处 `<img>` 无 `loading` 属性。两步走：公共组件 `ImageWithFallback` 加默认懒加载（覆盖其所有调用点），其余直接写 `<img>` 的位置逐个补。

**Files:**
- Modify: `loohii/src/app/components/figma/ImageWithFallback.tsx:25`
- Modify（每处 `<img` 标签加 `loading="lazy" decoding="async"`）:
  - `src/app/features/canvas/canvasUtils.tsx:3340`
  - `src/app/features/canvas/components/AssetMiniList.tsx:172`
  - `src/app/features/canvas/components/CharacterPropPickerPanel.tsx:93`
  - `src/app/features/canvas/components/ClipStoryboardList.tsx:611`
  - `src/app/features/canvas/nodes/CharacterNode.tsx:232,257,395`
  - `src/app/features/canvas/nodes/GenerationNode.tsx:782,832,1065`
  - `src/app/features/canvas/nodes/ImageInputNode.tsx:175`
  - `src/app/features/canvas/nodes/SceneNode.tsx:63,83`
  - `src/app/features/canvas/nodes/VideoNode.tsx:664`
  - `src/app/features/settings/PresetTab.tsx:49,109`
  - `src/app/features/settings/ProfileTab.tsx:38`
  - `src/app/features/settings/TeamTab.tsx:26,37,55`
  - `src/app/layouts/MainLayout.tsx:199`
  - `src/app/pages/DashboardPage.tsx:126`
  - `src/app/pages/LandingPage.tsx:63`
  - `src/app/pages/ProjectCanvasPage.tsx:5666,5697,5750,6105,6173`
  - `src/app/features/canvas/canvasHelpers.ts` 如有对应位置同步（该文件是 canvasUtils 的孪生，阶段 3 才合并，本任务两处都改以保持一致）

**Interfaces:**
- Produces: 视口外图片延迟加载；调用方仍可显式传 `loading="eager"` 覆盖

- [ ] **Step 1: ImageWithFallback 默认懒加载**

`src/app/components/figma/ImageWithFallback.tsx` 第 25 行改为：

```tsx
    <img loading="lazy" decoding="async" src={src} alt={alt} className={className} style={style} {...rest} onError={handleError} />
```
（`loading`/`decoding` 放在 `{...rest}` 之前，调用方传入同名 prop 时可覆盖默认值。）

- [ ] **Step 2: 批量补齐直接 img 标签**

对上面列出的每个位置，把 `<img` 改为 `<img loading="lazy" decoding="async"`。注意：若该 img 是"首屏必现的关键图"（LandingPage 首屏 hero 图 `LandingPage.tsx:63`），改用 `loading="eager"`，其余全部 lazy。

完成后验证无遗漏：
```bash
cd "H:\claude项目\loohii" && grep -rn "<img" src/app --include="*.tsx" | grep -v "loading=" | grep -v ImageWithFallback
```
Expected: 无输出（或仅剩明确豁免项）。

- [ ] **Step 3: 构建 + 手动验证**

```bash
cd "H:\claude项目\loohii" && npm run build
```
本地 dev：打开有多条生成记录的画布页 → DevTools Network → Img 过滤。
Expected: 仅视口内图片发起请求，滚动时增量加载。

- [ ] **Step 4: Commit**

```bash
cd "H:\claude项目\loohii" && git add -A src/app && git commit -m "perf: lazy-load images across canvas, settings and dashboard"
```

---

### Task 6: Dashboard 预取画布 chunk

`ProjectCanvasPage` chunk 615KB，路由懒加载导致进画布前白屏。Dashboard 挂载后空闲时预取。

**Files:**
- Modify: `loohii/src/app/pages/DashboardPage.tsx`（组件函数体内加一个 `useEffect`；该文件已有 React import，确认 `useEffect` 在 import 列表中，没有则补）

**Interfaces:**
- Consumes: `src/app/routes.tsx:10` 已存在的动态导入路径 `./pages/ProjectCanvasPage`（从 DashboardPage 引用时为 `./ProjectCanvasPage`）

- [ ] **Step 1: 加预取 effect**

在 `DashboardPage` 组件函数体顶部（其他 hooks 之后）加入：

```tsx
  useEffect(() => {
    // 空闲时预取画布页 chunk，消除路由切换白屏
    const idle = (cb: () => void) =>
      'requestIdleCallback' in window ? window.requestIdleCallback(cb) : window.setTimeout(cb, 1500);
    idle(() => { void import('./ProjectCanvasPage'); });
  }, []);
```

- [ ] **Step 2: 构建 + 验证**

```bash
cd "H:\claude项目\loohii" && npm run build && npm run dev
```
浏览器登录进入 Dashboard，DevTools Network → JS 过滤。
Expected: 停留 Dashboard 约 2 秒内出现 `ProjectCanvasPage-*.js` 请求；随后点进画布页，Network 中该 chunk 标记 `(memory cache)` 或 `(disk cache)`，页面即时渲染。

- [ ] **Step 3: Commit**

```bash
cd "H:\claude项目\loohii" && git add src/app/pages/DashboardPage.tsx && git commit -m "perf: prefetch canvas page chunk from dashboard on idle"
```

---

### Task 7: 部署阶段 1 并验收

**Files:**
- 无代码改动；操作生产服务器

**Interfaces:**
- Consumes: Task 3-6 的全部 commits（已在本地 main）

- [ ] **Step 1: 推送**

```bash
cd "H:\claude项目\loohii" && git push origin main && git rev-parse --short HEAD
```
Expected: push 成功，记下 SHA（下文 `<sha>`）。

- [ ] **Step 2: 服务器拉取并构建新镜像（按 SHA 打 tag 供回滚）**

```bash
PLINK "cd /projects/loohii && git pull && docker compose -f docker-compose.production.yml build app && docker tag loohii-app:latest loohii-app:<sha>"
```
Expected: build 成功结尾无 error；`docker images | grep loohii-app` 出现 `<sha>` tag。

- [ ] **Step 3: 重启并健康检查**

```bash
PLINK "cd /projects/loohii && docker compose -f docker-compose.production.yml up -d app && sleep 5 && curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:3001 && docker logs loohii-app --tail 5"
```
Expected: `200`；日志无启动错误。

- [ ] **Step 4: 线上冒烟验收**

浏览器访问 https://loohii.com：
1. 登录 → 打开一个真实项目画布：拖动节点流畅，节点选中/编辑正常
2. DevTools Network：空闲画布页 `generation-records` 请求仍每 5s 一次（阶段 4 才改），但 React DevTools 确认页面不再随轮询重渲染
3. 图片滚动增量加载；Dashboard 停留后进画布无白屏
Expected: 全部通过。

- [ ] **Step 5: 回滚预案（仅记录，不执行）**

若线上异常：
```bash
PLINK "docker tag loohii-app:<上一个sha> loohii-app:latest && cd /projects/loohii && docker compose -f docker-compose.production.yml up -d app"
```

- [ ] **Step 6: 标记阶段完成**

```bash
cd "H:\claude项目\loohii" && git tag phase-1-done && git push origin phase-1-done
```
