# 鹿绘AI 阶段4+5：数据层（TanStack Query + socket 推送）+ 全站 UI 焕新 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 TanStack Query + socket.io 推送替代画布页 5s 轮询（阶段4）；按已确认的"风格 A 精致暗黑"mockup 令牌化焕新全站 6 页 UI（阶段5）。

**Architecture:** 阶段4 —— 前端挂 `QueryClientProvider`，生成记录改为 `useGenerationRecords` query（staleTime 30s、60s 兜底轮询）；服务端在 Generation 状态变更处向 `project:{id}` 房间 emit `generation:updated`，前端收到后 invalidate query。阶段5 —— 所有视觉值收敛到 `src/styles/theme.css` 令牌 + 少量 `.lh-*` 组件类，先改 ui 原语（button/card），再逐页替换硬编码色值，画布页只换令牌与节点样式不动布局逻辑。

**Tech Stack:** @tanstack/react-query v5、socket.io 4.8（服务端已装）、socket.io-client（新增）、Tailwind CSS v4（CSS-first，无 config 文件）、shadcn/cva。

## Global Constraints

- 仓库：`H:\claude项目\loohii`，分支 main。当前基线 tag `phase-3-done`（4586b65）。
- **部署只用裸 `docker run`，禁止 docker compose**（服务器 compose 已坏）。标准重建命令见 Task 6/13。
- SSH：`PLINK` = `plink -ssh -batch -hostkey "SHA256:oMogBHYLu9S5widJ1D2MopEELwkNTb0EPS7OYnIzbJI" root@157.254.234.105 -pw "KZczfxxh7XnPcnEK"`。服务器构建仓库目录：`/projects/loohii`；env 文件：`/root/loohii-repeat-to-157-20260629-095447/meta/loohii-app.env`。
- 测试基线：`npx tsx --test server/src/**/*.test.ts src/**/*.test.ts`（或按现有脚本）中 workflows.test.ts 有 **11 个既有失败**（prompt 格式断言，与本计划无关），不计入回归。前端验证以 `npx vite build` 通过为准。
- lockfile 纪律：改依赖的任务先 `git checkout -- package-lock.json` 再安装，package.json 与 package-lock.json 同一提交；其他任务**绝不**提交 package-lock.json。`.env.local` 永不提交。
- Windows 环境：Git Bash 的 `/tmp` 对 node 不可见（用 `$TEMP`）；回环用 `127.0.0.1` 不用 `::1`。
- commit message：中文 conventional commits（`feat:` / `fix:` / `refactor:` / `style:` / `docs:`）。
- 设计令牌精确值（阶段5 全部任务的约束，逐字使用）：
  - 背景层级：画布底 `#0A0A0C` / 页面 `#0D0D0F` / 侧栏 `#141417` / 卡片渐变 `linear-gradient(180deg,#1C1C21,#17171B)` / 节点渐变 `linear-gradient(180deg,#1C1C21,#151519)`
  - 主色 `#F5A623`；主按钮渐变 `linear-gradient(135deg,#F5A623,#E08D0C)`，文字 `#0D0D0F`，投影 `0 4px 16px rgba(245,166,35,.3)`
  - 描边：常态 `#2A2A30`（节点 `#2E2E34`）；活跃/选中 `#F5A62366` + 辉光 `0 0 24px rgba(245,166,35,.14)`（节点选中 `#F5A62388` + `0 0 28px rgba(245,166,35,.18)`）——**辉光只出现在进行中/选中态（克制原则）**
  - 圆角：卡片 16px / 画布节点 14px / 按钮 10px / 小标签 6-7px（`--radius: 0.75rem`，配合现有 sm/md/lg/xl = −4/−2/0/+4px 公式 → 8/10/12/16px）
  - 状态色：生成中金色脉冲点；成功 `#7ED887`；失败沿用 `--destructive #EF4444`
  - 文字：页标题 800 字重（`font-extrabold`）；辅助文字 `#6B6B72`；小标签 9-11px
  - 画布点阵：`radial-gradient(circle,#1E1E22 1px,transparent 1px)`，间距 18px
  - mockup 参考：`H:\claude项目\.superpowers\brainstorm\1250-1783262470\content\style-a-detail.html`
- 阶段4 验收：空闲画布页 Network 面板无周期性 5s `/api/generation-records` 请求（只剩 60s 兜底）；生成完成后记录秒级出现。
- 阶段5 验收：与 mockup 逐页比对；画布布局逻辑零改动。

## 与设计文档的偏差（已按代码调研修正，执行前需人工确认）

1. **`?episodeId=` 参数不下沉服务端**。Generation 表没有 episodeId 列，剧集身份存于 input/parameters JSON 的 `sourceEpisodeId`，且无元数据的老记录按"episode-001"兜底（canvasUtils.tsx `generationRecordBelongsToEpisode`）。服务端 JSON-path 过滤 + 兜底语义复刻风险高收益低，剧集过滤保留客户端 `useMemo`。
2. **VideoNode 15s 轮询保留**。它轮询的是即梦(Dreamina)任务状态（`generateCanvasVideo(submitId)`），且**该轮询本身驱动服务端查询任务并落库**——改为订阅记录 query 会导致视频永不完成。不动。
3. **`useCanvasScene` / `useEpisodeSwitch` hooks 提取推迟**。ProjectCanvasPage 6783 行、闭包耦合面大，与数据层迁移同批提取回归风险高。本计划只做生成记录数据流迁移（本身即删除最大的轮询块）；剩余提取列入后续技术债。
4. **socket 事件名**：服务端既有基础设施按状态命名（`generation:queued/active/completed/failed`）但从未被调用；本计划按设计文档统一新增 `generation:updated`（负载仅 `{projectId, generationId, status}`，无敏感内容），既有事件体系不动。

---

# Part A · 阶段 4 数据层

### Task 1: 安装依赖 + QueryClientProvider

**Files:**
- Modify: `package.json`、`package-lock.json`
- Create: `src/app/lib/queryClient.ts`
- Modify: `src/app/App.tsx`

**Interfaces:**
- Produces: `queryClient`（模块级单例，供 Task 4 的 `invalidateGenerationRecords` 使用）；`<QueryClientProvider>` 挂根部。

- [ ] **Step 1: 还原 lockfile 漂移并安装依赖**

```bash
cd /h/claude项目/loohii
git checkout -- package-lock.json
npm install @tanstack/react-query socket.io-client
```

- [ ] **Step 2: 新建 queryClient**

```ts
// src/app/lib/queryClient.ts
import { QueryClient } from "@tanstack/react-query";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});
```

- [ ] **Step 3: App.tsx 挂 Provider**

当前 `src/app/App.tsx` 只有 `<RouterProvider router={router} />`（外层一个 div）。改为：

```tsx
import { QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "react-router";
import { router } from "./routes";
import { queryClient } from "./lib/queryClient";

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      {/* 保留原有外层 div 与 className 原样包裹 RouterProvider */}
      <RouterProvider router={router} />
    </QueryClientProvider>
  );
}
```

（以实际 App.tsx 现状为准，只加 Provider 包裹，其余不动。import 路径按文件内既有写法。）

- [ ] **Step 4: 构建验证**

Run: `npx vite build`
Expected: 构建通过，无类型/导入错误。

- [ ] **Step 5: Commit**

```bash
git add package.json package-lock.json src/app/lib/queryClient.ts src/app/App.tsx
git commit -m "feat: 引入 TanStack Query 与 socket.io-client，根部挂 QueryClientProvider（阶段4 Task 1）"
```

---

### Task 2: 服务端 `generation:updated` 推送（helper + 全部状态变更点接线）

**Files:**
- Create: `server/src/events/notifyGenerationUpdated.ts`
- Create: `server/src/events/notifyGenerationUpdated.test.ts`
- Modify: `server/src/routes/workflows.ts`（约 8 处状态变更点）
- Modify: `server/src/routes/generations.ts`（3 处）
- Modify: `server/src/routes/canvas.ts`（1 处）

**Interfaces:**
- Consumes: `app.set("realtime", realtime)`（server/src/index.ts:12-16 已存在，`realtime.io` 类型为 `RealtimeServerLike`，有 `to(room).emit(ev, payload)`）；`projectRoom`/`userRoom` 来自 `server/src/events/index.js` 导出。
- Produces: `notifyGenerationUpdated(app, { projectId, userId, generationId, status })` → 向 `project:{projectId}` 与 `user:{userId}` 房间 emit 事件 `"generation:updated"`，负载 `{ projectId, generationId, status }`。Task 3/4 的前端监听依赖此事件名与负载字段。

- [ ] **Step 1: 写失败测试**

```ts
// server/src/events/notifyGenerationUpdated.test.ts
import test from "node:test";
import assert from "node:assert/strict";
import { notifyGenerationUpdated } from "./notifyGenerationUpdated.js";

function fakeApp(realtime: unknown) {
  return { get: (key: string) => (key === "realtime" ? realtime : undefined) } as never;
}

test("emit 到 project 与 user 房间", () => {
  const emits: Array<[string, string, unknown]> = [];
  const realtime = {
    io: { to: (room: string) => ({ emit: (ev: string, p: unknown) => emits.push([room, ev, p]) }) },
  };
  notifyGenerationUpdated(fakeApp(realtime), {
    projectId: "p1", userId: "u1", generationId: "g1", status: "SUCCEEDED",
  });
  assert.equal(emits.length, 2);
  assert.deepEqual(emits[0], ["project:p1", "generation:updated", { projectId: "p1", generationId: "g1", status: "SUCCEEDED" }]);
  assert.equal(emits[1][0], "user:u1");
});

test("realtime 缺失时不抛错", () => {
  assert.doesNotThrow(() => {
    notifyGenerationUpdated(fakeApp(undefined), { projectId: "p1" });
  });
});

test("无 projectId/userId 时零 emit", () => {
  const emits: unknown[] = [];
  const realtime = { io: { to: () => ({ emit: (..._a: unknown[]) => emits.push(1) }) } };
  notifyGenerationUpdated(fakeApp(realtime), { generationId: "g1" });
  assert.equal(emits.length, 0);
});
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd /h/claude项目/loohii && npx tsx --test server/src/events/notifyGenerationUpdated.test.ts`
Expected: FAIL（模块不存在）。

- [ ] **Step 3: 实现 helper**

```ts
// server/src/events/notifyGenerationUpdated.ts
import type { Express } from "express";
import { projectRoom, userRoom } from "./index.js";

export interface GenerationUpdatedPayload {
  projectId?: string | null;
  userId?: string | null;
  generationId?: string;
  status?: string;
}

interface RealtimeLike {
  io: { to(room: string): { emit(event: string, payload: unknown): void } };
}

export function notifyGenerationUpdated(app: Express, payload: GenerationUpdatedPayload): void {
  try {
    const realtime = app.get("realtime") as RealtimeLike | undefined;
    if (!realtime?.io) return;
    const body = {
      projectId: payload.projectId ?? undefined,
      generationId: payload.generationId,
      status: payload.status,
    };
    if (payload.projectId) realtime.io.to(projectRoom(payload.projectId)).emit("generation:updated", body);
    if (payload.userId) realtime.io.to(userRoom(payload.userId)).emit("generation:updated", body);
  } catch {
    // 实时通知失败绝不阻塞主流程
  }
}
```

注意：若 `server/src/events/index.ts` 未导出 `projectRoom`/`userRoom`，从 `generationEvents.ts` 直接导入（先看 `server/src/events/` 目录现状）。

- [ ] **Step 4: 跑测试确认通过**

Run: `npx tsx --test server/src/events/notifyGenerationUpdated.test.ts`
Expected: PASS 3/3。

- [ ] **Step 5: 接线全部状态变更点**

规则：每处 `prisma.generation.update/create` 使状态进入或离开 QUEUED/RUNNING/SUCCEEDED/FAILED/CANCELED 后，追加一行（fire-and-forget，不 await 不 try 包裹——helper 内部已吞错）：

```ts
notifyGenerationUpdated(req.app, { projectId: <该记录的projectId>, userId: <userId>, generationId: <id>, status: <新状态> });
```

按**内容**定位（行号会漂移），全部站点：
1. `workflows.ts` 图片生成流 A：创建 RUNNING（约 :976 附近）后；标 FAILED（约 :1031-1034）后。
2. `workflows.ts` 图片生成流 B：RUNNING（约 :1240）；成功 update（约 :1265）；FAILED（约 :1339-1342）。
3. `workflows.ts` 画布图片生成：RUNNING（约 :1593）；SUCCEEDED（约 :1643-1647）；FAILED（约 :1680-1683）。
4. `workflows.ts` 画布视频：FAILED（约 :9825-9828）；SUCCEEDED（约 :9904-9908）。
5. `workflows.ts` 过期清扫 `updateMany` RUNNING→FAILED（约 :11244-11275）：在 updateMany **前**先 `findMany` 出受影响记录的 `{ id, projectId, userId }`，updateMany 后对每条调用 helper（status "FAILED"）。清扫函数若无 `req`，取它可访问的 Express app 实例（看该函数如何被调用；若拿不到 app，从 `app.set("realtime")` 同源处传入——最小改动优先，实在拿不到就跳过该站点并在报告说明）。
6. `generations.ts`：PATCH 更新状态（约 :136）、retry→QUEUED（约 :152）、delete→CANCELED（约 :168）。
7. `canvas.ts`：SUCCEEDED（约 :182）。

- [ ] **Step 6: 类型检查 + 全量服务端测试**

Run: `npm run server:check && npx tsx --test server/src/**/*.test.ts`
Expected: 类型通过；除 workflows.test.ts 既有 11 失败外全部 PASS。

- [ ] **Step 7: Commit**

```bash
git add server/src/events/notifyGenerationUpdated.ts server/src/events/notifyGenerationUpdated.test.ts server/src/routes/workflows.ts server/src/routes/generations.ts server/src/routes/canvas.ts
git commit -m "feat: 生成状态变更实时推送 generation:updated 到 project/user 房间（阶段4 Task 2）"
```

---

### Task 3: `project:subscribe` 服务端处理器 + 前端 realtime 客户端

**Files:**
- Modify: `server/src/realtime/socketServer.ts`（handleConnection 内加一个事件处理器，约 :97 旁）
- Create: `src/app/lib/realtimeClient.ts`

**Interfaces:**
- Consumes: socketServer 现状——默认握手只读 `auth.token/userId` 并进 `user:{id}` 房间，**不进 project 房间**；已有 `generation:subscribe` 处理器可仿写（socketServer.ts:97-115）。
- Produces: 服务端支持客户端 `socket.emit("project:subscribe", { projectId })` 进入 `project:{projectId}` 房间；前端导出 `subscribeProjectGenerationUpdates(projectId, onUpdate): () => void`（Task 4/5 消费）。

- [ ] **Step 1: 服务端加 project:subscribe（仿 generation:subscribe）**

在 `handleConnection` 中 `generation:subscribe` 注册的旁边加：

```ts
socket.on("project:subscribe", (payload: unknown) => {
  const projectId = getStringField(payload, "projectId");
  if (projectId) {
    void socket.join(projectRoom(projectId));
  }
});
```

- [ ] **Step 2: 前端 realtime 客户端**

```ts
// src/app/lib/realtimeClient.ts
import { io, type Socket } from "socket.io-client";

let socket: Socket | null = null;

function getRealtimeSocket(): Socket {
  if (!socket) {
    // 同源连接；path 用 socket.io 默认 /socket.io（服务端未自定义 path）。
    // websocket 优先，nginx 未配 upgrade 时自动回退 long-polling。
    socket = io({ transports: ["websocket", "polling"] });
  }
  return socket;
}

/** 订阅某项目的生成更新；返回取消函数。断线重连后自动重新入房。 */
export function subscribeProjectGenerationUpdates(
  projectId: string,
  onUpdate: (payload: { projectId?: string; generationId?: string; status?: string }) => void,
): () => void {
  const s = getRealtimeSocket();
  const subscribe = () => s.emit("project:subscribe", { projectId });
  const handler = (payload: unknown) => {
    const p = payload as { projectId?: string };
    if (p?.projectId === projectId) onUpdate(p);
  };
  subscribe();
  s.on("connect", subscribe);
  s.on("generation:updated", handler);
  return () => {
    s.off("connect", subscribe);
    s.off("generation:updated", handler);
  };
}
```

- [ ] **Step 3: 本地开发代理检查**

看 `vite.config.ts`：若存在 `/api` 的 dev proxy，则为 `/socket.io` 追加同目标代理项（`ws: true`）；若不存在 proxy 配置则跳过此步。

- [ ] **Step 4: 验证**

Run: `npm run server:check && npx vite build`
Expected: 均通过。

- [ ] **Step 5: Commit**

```bash
git add server/src/realtime/socketServer.ts src/app/lib/realtimeClient.ts vite.config.ts
git commit -m "feat: socket 支持 project:subscribe 入房，前端 realtime 订阅客户端（阶段4 Task 3）"
```

---

### Task 4: `useGenerationRecords` hook + 画布页迁移（删除 5s 轮询与 window 事件）

**Files:**
- Create: `src/app/lib/queries/generationRecords.ts`
- Modify: `src/app/pages/ProjectCanvasPage.tsx`（删 5s 轮询效果块，state→派生 memo，替换 setGenerationRecords/事件派发站点）
- Modify: `src/app/features/canvas/nodes/GenerationNode.tsx`（4 处事件派发→invalidate）
- Modify: `src/app/features/canvas/canvasUtils.tsx`（删除 `CANVAS_GENERATION_RECORDS_REFRESH_EVENT` 常量 :433）
- Modify: `src/app/features/canvas/nodes/shared.tsx`（删该常量 import，:28）
- Delete: `src/app/features/canvas/generationRecordsFingerprint.ts` 与 `generationRecordsFingerprint.test.ts`

**Interfaces:**
- Consumes: Task 1 `queryClient`；Task 3 `subscribeProjectGenerationUpdates`；`apiClient.listGenerationRecords(projectId, { limit, compact })`（src/app/lib/api/generationApi.ts:8）；剧集过滤函数 `generationRecordBelongsToEpisode(record, episodeId, episodeTitle)`（canvasUtils.tsx:5227）与 `generationRecordMatchesActiveCanvasGeneration(record, activeGenerationKeys)`。
- Produces: `generationRecordsQueryKey(projectId)`、`useGenerationRecords(projectId)`、`invalidateGenerationRecords(projectId)`（Task 5 与 GenerationNode 消费）。

- [ ] **Step 1: 新建 queries 模块**

```ts
// src/app/lib/queries/generationRecords.ts
import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { apiClient } from "../api";
import type { GenerationRecord } from "../api";
import { queryClient } from "../queryClient";
import { subscribeProjectGenerationUpdates } from "../realtimeClient";

export const generationRecordsQueryKey = (projectId: string) =>
  ["generation-records", projectId] as const;

export function invalidateGenerationRecords(projectId: string | undefined): void {
  if (!projectId || projectId === "local") return;
  void queryClient.invalidateQueries({ queryKey: ["generation-records", projectId] });
}

/** 画布页生成记录：30s stale + 60s 兜底轮询 + socket 推送 invalidate。 */
export function useGenerationRecords(projectId: string | undefined) {
  const enabled = !!projectId && projectId !== "local";
  const client = useQueryClient();

  useEffect(() => {
    if (!enabled || !projectId) return;
    return subscribeProjectGenerationUpdates(projectId, () => {
      void client.invalidateQueries({ queryKey: generationRecordsQueryKey(projectId) });
    });
  }, [enabled, projectId, client]);

  return useQuery<GenerationRecord[]>({
    queryKey: generationRecordsQueryKey(projectId ?? "none"),
    queryFn: () => apiClient.listGenerationRecords(projectId, { limit: 120, compact: true }),
    enabled,
    staleTime: 30_000,
    refetchInterval: 60_000,
    placeholderData: keepPreviousData,
  });
}
```

（`apiClient` / `GenerationRecord` 的实际导出名以 `src/app/lib/api/index.ts` 为准。）

- [ ] **Step 2: ProjectCanvasPage 迁移**

1. **删除** 5s 轮询效果块（约 :1108-1143，特征：`window.setInterval(loadRecords, 5000)` + `CANVAS_GENERATION_RECORDS_REFRESH_EVENT` 监听 + `generationRecordsFingerprint`）。
2. **删除** `const [generationRecords, setGenerationRecords] = useState<GenerationRecord[]>([])`（约 :450），改为派生：

```ts
const { data: allGenerationRecords } = useGenerationRecords(projectId);
const generationRecords = useMemo(() => {
  const records = allGenerationRecords ?? [];
  return records.filter((record) =>
    generationRecordBelongsToEpisode(record, activeEpisodeId, selectedEpisode) ||
    generationRecordMatchesActiveCanvasGeneration(record, activeGenerationKeys),
  );
}, [allGenerationRecords, activeEpisodeId, selectedEpisode, activeGenerationKeys]);
```

（`activeGenerationKeys` 沿用原轮询块中同名的既有来源；若原实现是在效果内部构造的，把该构造逻辑一并挪进此 memo 或其依赖 memo。）
3. **替换其余 `setGenerationRecords` 站点**：
   - 剧集切换清空（`loadEpisodeWorkspace` 内约 :928）：直接删除该行（过滤 memo 会随 `activeEpisodeId` 自动重算）。
   - 两处内联刷新（约 :2997-3002、:3347-3351，特征：`listGenerationRecords(projectId, { limit: 300, compact: true })` 后过滤并 setState）：**保留**其本地 `apiClient.listGenerationRecords` 调用与后续本地逻辑（局部逻辑要用拉到的数组），仅把末尾 `setGenerationRecords(filtered)` 替换为 `invalidateGenerationRecords(projectId)`。
   - 其余任何 `setGenerationRecords` 残留：同理换 invalidate 或删除，逐处判断并在报告列出。
4. **替换事件派发**：`window.dispatchEvent(new Event(CANVAS_GENERATION_RECORDS_REFRESH_EVENT))` 共 7 处（ProjectCanvasPage :1079、:2765、:2778、:4965；GenerationNode :507、:533、:570、:601——以 grep 实际结果为准），全部替换为 `invalidateGenerationRecords(projectId)`（GenerationNode 内用其作用域内的 projectId prop/变量）。
5. **删除常量与孤儿**：canvasUtils.tsx:433 的常量定义、shared.tsx:28 的 import、`generationRecordsFingerprint.ts` 及其 test 文件（该函数仅被已删的轮询块使用——删除前 grep 确认零引用）。

- [ ] **Step 3: 全局 grep 验证零残留**

Run: `grep -rn "CANVAS_GENERATION_RECORDS_REFRESH_EVENT\|generationRecordsFingerprint\|setGenerationRecords" src/ | grep -v test`
Expected: 无输出。

- [ ] **Step 4: 构建 + 测试**

Run: `npx vite build && npx tsx --test src/app/lib/thumbUrl.test.ts`
Expected: 构建通过；现存前端测试不回归。

- [ ] **Step 5: Commit**

```bash
git add src/app/lib/queries/generationRecords.ts
git add -u src
git commit -m "feat: 画布页生成记录迁移 TanStack Query + socket 推送，移除 5s 轮询与 window 刷新事件（阶段4 Task 4）"
```

---

### Task 5: 生成记录页迁移同一 query 体系

**Files:**
- Modify: `src/app/pages/ProjectRecordsPage.tsx`（:62 附近的一次性 `listGenerationRecords(projectId)` 挂载拉取）

**Interfaces:**
- Consumes: Task 3 `subscribeProjectGenerationUpdates`、Task 4 的 key 约定（本页用独立 key `["generation-records", projectId, "full"]`，因为它拉全量非 compact）。

- [ ] **Step 1: 替换挂载拉取为 useQuery + 推送 invalidate**

```tsx
const client = useQueryClient();
const { data: records = [], isLoading, refetch } = useQuery({
  queryKey: ["generation-records", projectId, "full"] as const,
  queryFn: () => apiClient.listGenerationRecords(projectId),
  enabled: !!projectId && projectId !== "local",
  staleTime: 30_000,
});

useEffect(() => {
  if (!projectId || projectId === "local") return;
  return subscribeProjectGenerationUpdates(projectId, () => {
    void client.invalidateQueries({ queryKey: ["generation-records", projectId, "full"] });
  });
}, [projectId, client]);
```

原有 loading/error state、删除/重试后的手动刷新逻辑改为 `refetch()` 或 invalidate；保持页面行为不变（以现文件实际结构为准做最小替换）。

- [ ] **Step 2: 构建验证**

Run: `npx vite build`
Expected: 通过。

- [ ] **Step 3: Commit**

```bash
git add src/app/pages/ProjectRecordsPage.tsx
git commit -m "feat: 生成记录页迁移 TanStack Query 并接入 socket 刷新（阶段4 Task 5）"
```

---

### Task 6: 部署阶段 4

**Files:** 无本地代码改动（deploy 任务）。

- [ ] **Step 1: 推送**

```bash
cd /h/claude项目/loohii && git push origin main
```

- [ ] **Step 2: nginx websocket 检查（不改则跳过）**

```bash
PLINK "grep -n 'Upgrade\|socket.io' /etc/nginx/nginx.conf /etc/nginx/conf.d/*.conf /etc/nginx/sites-enabled/* 2>/dev/null"
```

若代理到 3001 的 location 缺 websocket 升级头，则备份后补（并 `nginx -t && systemctl reload nginx`）：

```nginx
proxy_http_version 1.1;
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection "upgrade";
```

若不便修改：socket.io 会自动回退 long-polling，功能不受影响——记录现状即可。

- [ ] **Step 3: 服务器构建 + 裸 docker run 重建**

```bash
PLINK "cd /projects/loohii && git pull && docker build -f Dockerfile.loohii -t loohii-app:latest -t loohii-app:\$(git rev-parse --short HEAD) ."   # 超时给足 600s
PLINK "docker stop loohii-app && docker rm loohii-app && docker run -d --name loohii-app --restart unless-stopped --network loohii_default --network-alias app -p 127.0.0.1:3001:3001 --env-file /root/loohii-repeat-to-157-20260629-095447/meta/loohii-app.env -v loohii_uploads:/var/lib/loohii/uploads loohii-app:\$(cd /projects/loohii && git rev-parse --short HEAD)"
```

- [ ] **Step 4: 冒烟**

```bash
curl -s -o /dev/null -w "%{http_code}" https://loohii.com/          # 期望 200
curl -s https://loohii.com/health                                   # 期望 ok:true
curl -s "https://loohii.com/socket.io/?EIO=4&transport=polling" | head -c 120   # 期望以 0{"sid": 开头（engine.io 握手）
```

- [ ] **Step 5: 打 tag**

```bash
cd /h/claude项目/loohii && git tag phase-4-done && git push origin phase-4-done
```

- [ ] **Step 6: 报告中注明人工验收项**

浏览器打开画布页：Network 面板空闲 2 分钟只应出现 ≤2 次 `/api/generation-records`（60s 兜底）；发起一张图生成，完成后记录应在 ~1s 内出现（socket 推送）。回滚镜像：`loohii-app:4586b65`。

---

# Part B · 阶段 5 全站 UI 焕新（风格 A）

逐页顺序（设计文档规定）：令牌/原语 → 登录 → Dashboard(+布局壳) → 项目创建 → 生成记录+设置 → 画布 → 部署。

### Task 7: 设计令牌 + ui 原语（button/card）+ index.html 修正 + favicon

**Files:**
- Modify: `src/styles/theme.css`
- Modify: `src/app/components/ui/button.tsx`
- Modify: `src/app/components/ui/card.tsx`
- Modify: `index.html`
- Create: `public/favicon.svg`（`public/` 目录当前不存在，需创建）

**Interfaces:**
- Produces: CSS 组件类 `.lh-card`、`.lh-glow-active`、`.lh-node`、`.lh-node-active`、`.lh-dot-pulse`；新令牌 `--color-canvas`、`--color-canvas-dot`；button `default` variant 变为品牌渐变。后续 Task 8-12 全部依赖这些类名。

- [ ] **Step 1: theme.css 令牌更新（精确值）**

在 `:root` 中修改/新增（其余令牌不动）：

```css
--border: #2A2A30;
--muted-foreground: #6B6B72;
--radius: 0.75rem;                    /* sm/md/lg/xl 公式不变 → 8/10/12/16px */
--color-layer-1: #141417;             /* 侧栏 */
--color-border-card: #2A2A30;
--color-brand-to: #E08D0C;
--color-status-success: #7ED887;
--color-canvas: #0A0A0C;
--color-canvas-dot: #1E1E22;
```

`@theme inline` 块中补映射（照既有格式）：

```css
--color-canvas: var(--color-canvas);
--color-canvas-dot: var(--color-canvas-dot);
```

文件末尾追加组件类：

```css
@layer components {
  .lh-card {
    background-image: linear-gradient(180deg, #1C1C21, #17171B);
    border-color: #2A2A30;
  }
  .lh-glow-active {
    border-color: #F5A62366;
    box-shadow: 0 0 24px rgba(245, 166, 35, 0.14);
  }
  .lh-node {
    background-image: linear-gradient(180deg, #1C1C21, #151519);
    border-color: #2E2E34;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);
  }
  .lh-node-active {
    border-color: #F5A62388;
    box-shadow: 0 0 28px rgba(245, 166, 35, 0.18);
  }
  .lh-dot-pulse {
    width: 8px;
    height: 8px;
    border-radius: 9999px;
    background: #F5A623;
    box-shadow: 0 0 8px #F5A623;
    animation: lh-pulse 1.6s ease-in-out infinite;
  }
  @keyframes lh-pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.35; }
  }
}
```

- [ ] **Step 2: button.tsx default variant 改品牌渐变**

`button.tsx:12` 的 `default` variant 类替换为：

```
"bg-[linear-gradient(135deg,#F5A623,#E08D0C)] text-[#0D0D0F] font-bold shadow-[0_4px_16px_rgba(245,166,35,.3)] hover:opacity-90"
```

其余 variant（destructive/outline/secondary/ghost/link）与 size 不动。顺手删掉 default variant 内永不生效的 `dark:` 前缀类（仓库无 `.dark` class）。

- [ ] **Step 3: card.tsx 接卡片渐变**

`card.tsx:5-16` 的 Card 容器 className 中，将 `bg-card` 替换为 `bg-card lh-card`（保留 rounded-xl —— 令牌调整后 = 16px ✓）。

- [ ] **Step 4: index.html 修正 + favicon**

- `<html lang="en">` → `<html lang="zh-CN">`
- `<head>` 补：

```html
<meta name="description" content="鹿绘AI —— AI 驱动的动画短剧创作平台：剧本拆解、分镜生成、图像与视频生成一站式完成。" />
<link rel="icon" type="image/svg+xml" href="/favicon.svg" />
```

- 新建 `public/favicon.svg`：

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#F5A623"/>
      <stop offset="1" stop-color="#E08D0C"/>
    </linearGradient>
  </defs>
  <rect width="64" height="64" rx="14" fill="url(#g)"/>
  <text x="32" y="43" font-family="system-ui,sans-serif" font-size="30" font-weight="800" fill="#0D0D0F" text-anchor="middle">鹿</text>
</svg>
```

- [ ] **Step 5: 构建验证**

Run: `npx vite build`
Expected: 通过；`dist/favicon.svg` 存在。

- [ ] **Step 6: Commit**

```bash
git add src/styles/theme.css src/app/components/ui/button.tsx src/app/components/ui/card.tsx index.html public/favicon.svg
git commit -m "style: 风格A设计令牌落地 theme.css，button/card 原语品牌化，index.html 语言/描述/favicon（阶段5 Task 7）"
```

---

### Task 8: 登录页焕新（AuthPage）

**Files:**
- Modify: `src/app/pages/AuthPage.tsx`（174 行）

**Interfaces:**
- Consumes: Task 7 的 `.lh-card`、button default variant（自动生效）。

- [ ] **Step 1: 按映射表替换**

| 目标元素 | 现状（以文件实际为准） | 改为 |
|---|---|---|
| 页面容器背景 | 任意硬编码/`bg-background` | `bg-background`（#0D0D0F，令牌已对） |
| 登录卡片 | 硬编码 bg/border | `lh-card rounded-xl border` |
| 页标题 | 现有字重 | `font-extrabold text-[#E8E8EC]` |
| 辅助/提示文字 | `text-muted-foreground` 或硬编码灰 | `text-[#6B6B72]`（或保留 `text-muted-foreground`——令牌已改为该值） |
| 提交按钮 | Button default | 不改（Task 7 已渐变化）；若页面用了自定义按钮类，替换为 `<Button>` default |
| 输入框 | 现有 Input | 不动结构，仅确认 focus ring 为 `--ring`（金色）即可 |

原则：**只改视觉类名与内联颜色，不改任何逻辑/表单行为**。逐字保留文案。

- [ ] **Step 2: 构建 + 本地目检**

Run: `npx vite build`（如可 `npx vite` 起 dev server 本地打开 /login 截图目检与 mockup 对照）
Expected: 构建通过。

- [ ] **Step 3: Commit**

```bash
git add src/app/pages/AuthPage.tsx
git commit -m "style: 登录页风格A焕新（阶段5 Task 8）"
```

---

### Task 9: 布局壳 + Dashboard 焕新（MainLayout + DashboardPage）

**Files:**
- Modify: `src/app/layouts/MainLayout.tsx`（741 行）
- Modify: `src/app/pages/DashboardPage.tsx`（169 行）

- [ ] **Step 1: MainLayout 映射替换**

| 位置 | 现状 | 改为 |
|---|---|---|
| 顶栏 :167 | `border-b border-[#1f1f23] bg-[#0f0f11]` | `border-b border-[#222226] bg-[#141417]` |
| 侧栏 :221 | `bg-[#0f0f11]` | `bg-[#141417]` |
| 侧栏激活项 :501 | `border-l-primary`（保留） | 保留，另加 `text-primary` 若未有 |
| Agent 面板 :283 | `bg-[#111113]` | `bg-[#141417]` |
| 各处 `border-[#1f1f23]` | 硬编码 | `border-[#222226]` 或 `border-border` |

（行号会漂移，按 grep `#0f0f11|#1f1f23|#111113` 逐个替换；MainLayout 内其余硬编码深灰底一律对齐 `#141417`/`#0D0D0F` 两级。）

- [ ] **Step 2: DashboardPage 映射替换**

| 元素 | 改为 |
|---|---|
| 项目卡片 | `lh-card rounded-xl border`（走 Card 组件的自动生效）；"生成中"的项目卡片额外 `lh-glow-active` |
| "+ 新建项目"按钮 | `<Button>` default（Task 7 渐变） |
| 页标题 | `font-extrabold` |
| 状态徽章（生成中） | `<span className="inline-flex items-center gap-1 rounded-[7px] border px-1.5 py-0.5 text-[10px] font-medium" style={{ background: "rgba(13,13,15,.75)", borderColor: "#7ED88733", color: "#7ED887" }}><span className="lh-dot-pulse" style={{ width: 6, height: 6 }} />生成中</span>` |
| 辅助文字 | `text-muted-foreground`（=#6B6B72） |

- [ ] **Step 3: 构建 + 目检 + Commit**

Run: `npx vite build` → PASS。

```bash
git add src/app/layouts/MainLayout.tsx src/app/pages/DashboardPage.tsx
git commit -m "style: 布局壳与 Dashboard 风格A焕新（阶段5 Task 9）"
```

---

### Task 10: 项目创建/设定页焕新（ProjectSetupPage）

**Files:**
- Modify: `src/app/pages/ProjectSetupPage.tsx`（653 行）

- [ ] **Step 1: 映射替换（同 Task 9 原则）**

- 所有卡片/分区容器 → `lh-card rounded-xl border`（或 Card 组件）
- 主操作按钮 → Button default；次级按钮 → variant secondary/outline 不动
- 页标题 `font-extrabold`；辅助文字对齐 `text-muted-foreground`
- 硬编码 `bg-[#...]`/`zinc-800/900` 底色 → `#141417`（面板）或 `#0D0D0F`（页面）两级；边框 → `border-border`
- 步骤指示/进行中状态若有 → 金色 `text-primary` + `lh-dot-pulse`
- **不改任何表单逻辑与提交行为**

- [ ] **Step 2: 构建 + Commit**

Run: `npx vite build` → PASS。

```bash
git add src/app/pages/ProjectSetupPage.tsx
git commit -m "style: 项目创建页风格A焕新（阶段5 Task 10）"
```

---

### Task 11: 生成记录页 + 设置页焕新

**Files:**
- Modify: `src/app/pages/ProjectRecordsPage.tsx`（586 行）
- Modify: `src/app/pages/SettingsPage.tsx`（60 行壳）
- Modify: `src/app/features/settings/` 下的 tab 组件（以 grep 硬编码色值结果为准）

- [ ] **Step 1: 生成记录页映射**

- 记录卡片/表格容器 → `lh-card rounded-xl border`
- 状态徽章：成功 `#7ED887`/`#7ED88733`、失败沿用 destructive、进行中金色 + `lh-dot-pulse`（复用 Task 9 徽章片段，颜色按状态替换：进行中 `borderColor:"#F5A62333", color:"#F5A623"`）
- 缩略图容器圆角 → `rounded-lg`
- 页标题 `font-extrabold`

- [ ] **Step 2: 设置页映射**

- Tab 导航激活态 → `text-primary border-primary`
- 表单卡片 → `lh-card rounded-xl border`
- 保存按钮 → Button default
- `grep -rn "bg-\[#\|zinc-8\|zinc-9" src/app/features/settings src/app/pages/SettingsPage.tsx` 逐个对齐两级底色

- [ ] **Step 3: 构建 + Commit**

Run: `npx vite build` → PASS。

```bash
git add src/app/pages/ProjectRecordsPage.tsx src/app/pages/SettingsPage.tsx src/app/features/settings
git commit -m "style: 生成记录页与设置页风格A焕新（阶段5 Task 11）"
```

---

### Task 12: 画布焕新（仅令牌与节点样式，不动布局逻辑）

**Files:**
- Modify: `src/app/features/canvas/nodes/*.tsx`（11 个节点文件：CharacterNode、GenerationNode、SceneNode、VideoNode、TranslationNode、PromptInspectorNode、PromptOptimizerNode、AgentNode、ImageInputNode、AudioInputNode、WorkflowNode）
- Modify: `src/app/features/canvas/nodes/shared.tsx`（青色 accents → 品牌金）
- Modify: `src/app/features/canvas/canvasUtils.tsx`（CanvasNodeResizer :3195-3220 颜色、CanvasHandle :3222-3247）
- Modify: `src/app/pages/ProjectCanvasPage.tsx`（ReactFlow 背景/Controls/MiniMap :5493-5503、内联表单输入 :6349-6442）

**约束：只改颜色/圆角/阴影类与内联色值，绝不改节点尺寸计算、拖拽、连接、resize 逻辑与任何 handler。**

- [ ] **Step 1: 节点容器统一**

11 个节点文件中的容器模式 `rounded-lg border border-border bg-[#141416] shadow-xl ... hover:border-<各色>` 统一替换为：

```
rounded-[14px] border lh-node transition-colors hover:border-[#3A3A40]
```

各节点原有 hover 专属色（sky/cyan/amber/violet 等）一律收敛为 `hover:border-[#3A3A40]`（克制原则——彩色只留给选中/进行中态）。节点内部子面板 `bg-zinc-900 border-zinc-800` → `bg-[#141417] border-[#26262B]`；`bg-[#101014]` → `bg-[#141417]`。

- [ ] **Step 2: 选中/进行中态金色化**

- 节点组件中"选中"或"生成中"条件类（各节点 `selected` prop / 生成中状态处）追加 `lh-node-active`；生成中的状态点用 `<span className="lh-dot-pulse" />`。
- `canvasUtils.tsx` CanvasNodeResizer：`color="#38bdf8"` → `color="#F5A623"`；handle 内联样式 `border 1px solid #7dd3fc` → `#F7C24E`；`background #09090b` 不动。
- CanvasHandle tone 类（:3234 附近）：`sky` 色调 → 金色 `!border-[#F5A623]`；其余 tone 保持。
- 进度条（GenerationNode 若有）：轨道 `#26262B`，条 `bg-[linear-gradient(90deg,#F5A623,#F7C24E)]`。

- [ ] **Step 3: shared.tsx 去青色**

`border-cyan-500/40` → `border-[#2E2E34]`；`focus:border-cyan-400` → `focus:border-primary`；保存按钮 `bg-cyan-500...` → Button default 或 `bg-[linear-gradient(135deg,#F5A623,#E08D0C)] text-[#0D0D0F] font-bold`。

- [ ] **Step 4: ReactFlow 画布 chrome**

ProjectCanvasPage :5493-5503：

- 画布容器底色 → `bg-[#0A0A0C]`
- `<Background color="#27272a" .../>` → `color="#1E1E22" gap={18}`
- Controls `!bg-[#141416] !border-zinc-800` → `!bg-[#141417] !border-[#26262B]`
- MiniMap maskColor/nodeColor 不动
- 内联表单输入 `bg-[#0d0d0f] border-zinc-800` → `bg-[#0D0D0F] border-[#26262B]`

- [ ] **Step 5: 构建 + 交互回归自检**

Run: `npx vite build` → PASS。
本地如可起 dev server：拖动节点、选中（应显金色辉光）、连线、resize 各试一次——纯样式改动不应影响任何交互。

- [ ] **Step 6: Commit**

```bash
git add src/app/features/canvas src/app/pages/ProjectCanvasPage.tsx
git commit -m "style: 画布节点与画布底风格A焕新——金色选中辉光、去杂色、点阵背景（阶段5 Task 12）"
```

---

### Task 13: 部署阶段 5 + 收尾

**Files:** 无本地代码改动（deploy 任务）。

- [ ] **Step 1: 推送 + 服务器构建 + 重建容器**

同 Task 6 Step 1/3（镜像 tag 用新 HEAD sha；build 超时 600s）。

- [ ] **Step 2: 冒烟**

```bash
curl -s -o /dev/null -w "%{http_code}" https://loohii.com/                 # 200
curl -s https://loohii.com/ | grep -o 'lang="zh-CN"'                        # 命中
curl -s -o /dev/null -w "%{http_code}" https://loohii.com/favicon.svg       # 200
curl -s https://loohii.com/health                                           # ok:true
```

- [ ] **Step 3: 打 tag**

```bash
cd /h/claude项目/loohii && git tag phase-5-done && git push origin phase-5-done
```

- [ ] **Step 4: 报告注明人工验收**

浏览器逐页（登录/Dashboard/项目创建/生成记录/设置/画布）与 mockup `style-a-detail.html` 比对：卡片渐变+16px 圆角、金色渐变主按钮、生成中金色脉冲+辉光、画布 #0A0A0C 点阵、节点选中金色辉光。回滚镜像：phase-4 的 sha tag。

---

## 风险与回滚

| 风险 | 应对 |
|---|---|
| socket 推送丢失/断连 | query 保留 60s 兜底 refetchInterval，最坏退化为慢一分钟 |
| nginx 无 websocket upgrade | socket.io 自动回退 long-polling，功能不受影响 |
| 迁移后记录时序变化 | 内联刷新站点保留原有拉取逻辑仅替换 setState；placeholderData 防闪烁 |
| project:subscribe 无鉴权（知道 projectId 即可入房） | 负载仅 `{projectId, generationId, status}` 三个 ID/枚举，无内容泄露；作为已知限制记录，后续可在 authenticate 回调校验 token |
| UI 改动破坏画布交互 | Task 12 严格只改样式类；部署前本地交互自检 |
| 每阶段独立部署 | 阶段4（Task 6）与阶段5（Task 13）各自 tag，可分别回滚 |
