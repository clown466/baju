# 鹿绘 AI 前端优化 + 全站 UI 焕新 · 设计文档

日期：2026-07-05
项目仓库：https://github.com/clown466/loohii （main 分支）
生产环境：157.254.234.105，Docker（loohii-app / loohii-postgres / loohii-redis），nginx 反代，域名 loohii.com

## 1. 背景与问题

生产环境审查发现：

- **画布卡顿**：`src/app/features/canvas/nodes/` 下 10 个 xyflow 自定义节点组件均未使用 `React.memo`，拖动/平移时全量重渲染。
- **轮询浪费**：`ProjectCanvasPage.tsx:1129` 每 5 秒拉取 `listGenerationRecords(limit=120)` 约 1.27MB JSON，客户端过滤后 `setGenerationRecords` 无条件设置新数组引用，即使数据未变也触发 6768 行巨型页面重渲染；`.catch` 时清空列表导致 UI 闪空。
- **无压缩无缓存**：nginx `gzip_types` 被注释（JSON 裸传）；静态资源 `Cache-Control: max-age=0`；7.5MB 参考图 PNG 原图直出且重复加载。
- **技术债**：`canvasUtils.tsx`（7426 行）与 `canvasHelpers.ts`（6556 行）为复制粘贴的孪生文件（开头 2000 字节 md5 相同），常量重复定义。
- **依赖冗余**：`motion` 与 `framer-motion` 并存（同一库两份）；`react-slick` 与 `embla-carousel` 两个轮播；MUI + Radix 双组件库。
- **视觉陈旧**：现有主题 #0D0D0F 底 + #F5A623 琥珀金 + 0.25rem 小圆角，缺乏层次与精致感。

## 2. 目标

- 性能：画布交互不卡顿；生成记录接口传输量降 80% 以上；图片走缩略图；路由切换预取。
- 架构：数据层迁移 TanStack Query + socket 推送；消除孪生文件；依赖去重。
- 视觉：全站 6 页（登录、Dashboard、项目创建、画布、生成记录、设置）统一焕新为「精致暗黑」风格。

## 3. 非目标（本期不做）

- MUI → Radix 迁移（仅产出使用量统计报告，供后续决策）。
- ProjectCanvasPage 的 JSX 布局结构重排（仅抽离数据 hooks）。
- 移动端适配。
- 全推送化（保留 60s 轮询兜底）。

## 4. 总体方案

采用「稳健渐进式」：保留轮询骨架但升级为 TanStack Query 管理，socket 推送触发即时 refetch；依赖只删无争议冗余；画布页只抽数据 hooks 不动 JSX；UI 焕新以 CSS 设计令牌为主、组件微调为辅。

## 5. 实施阶段（逐阶段部署上线）

### 阶段 0 · 准备
- 服务器 `/projects/loohii` 现有 5 个未提交改动（agent.ts、characters.ts、workflows.ts、workflows.test.ts、canvasHelpers.ts）commit 并 push 到 GitHub。
- 本地克隆仓库，docker compose 启动本地 postgres/redis，跑通 `npm run dev` + `server:dev`。
- 验收：本地环境可登录、可打开画布。

### 阶段 1 · 性能快赢（纯前端）
- 10 个画布节点组件全部 `export default memo(XxxNode)`；排查传入节点的内联对象/函数 props。
- 轮询结果指纹比较：以 `id+updatedAt` 拼接指纹，与上次相同则跳过 `setGenerationRecords`。
- `.catch` 不再清空记录，保留旧数据。
- 全站 `<img>` 补 `loading="lazy"` + `decoding="async"`（列表、缩略场景）。
- Dashboard 挂载后动态 `import()` 预取 ProjectCanvasPage chunk。
- 验收：React DevTools Profiler 确认拖动单个节点时其他节点不重渲染；网络异常时记录列表不闪空。

### 阶段 2 · 网络与图片（nginx + 服务端）
- nginx：启用 `gzip_types`（含 application/json、text/css、application/javascript 等）、`gzip_comp_level 6`、`gzip_vary on`。
- nginx：`/assets/` 带 hash 产物 `Cache-Control: public, max-age=31536000, immutable`；uploads 图片由 nginx 直接 serve（alias 到 `/var/lib/loohii/uploads`，容器卷同源）并加长缓存。
- 服务端：上传/生成落盘时用 sharp 生成 WebP 缩略图两档（300px、1024px），命名约定 `<原名>.thumb300.webp` / `<原名>.thumb1024.webp`；API 返回缩略图 URL 字段；前端列表与画布节点使用缩略图，点开详情才加载原图。
- 存量图片：一次性脚本批量补生成缩略图。
- 验收：生成记录接口传输 <200KB；图片列表请求为 WebP 缩略图；重复访问静态资源命中缓存。

### 阶段 3 · 技术债清理
- diff `canvasUtils.tsx` 与 `canvasHelpers.ts`，合并为单一模块（保留差异部分），全局更新 import，删除冗余文件。
- 删除 `motion` 包（保留 `framer-motion`），统一 import 来源。
- 删除 `react-slick`（保留 `embla-carousel-react`），迁移其使用点。
- 产出 MUI 组件使用量报告（grep 统计 `@mui` import），不迁移。
- 验收：`npm run build` 通过；全站冒烟无异常；canvas chunk 体积下降。

### 阶段 4 · 数据层架构
- 引入 `@tanstack/react-query`，`QueryClientProvider` 挂应用根部；新建 `src/app/lib/queries/` 目录。
- `useGenerationRecords(projectId, episodeId)`：queryKey `['generation-records', projectId, episodeId]`；服务端 `listGenerationRecords` 增加 `?episodeId=` 参数，过滤下沉到后端；`staleTime: 30_000`、`refetchInterval: 60_000`（兜底）、`placeholderData: keepPreviousData`。
- socket 推送：服务端在生成状态变更时 emit `generation:updated { projectId }`；前端监听并 `queryClient.invalidateQueries(['generation-records', projectId])`。替代 5s 轮询与 `CANVAS_GENERATION_RECORDS_REFRESH_EVENT` window 事件。
- VideoNode 15s 自轮询改为订阅统一 query，多个视频节点共享一路请求。
- ProjectCanvasPage 抽离 `useGenerationRecords`、`useCanvasScene`、`useEpisodeSwitch` 等 hooks（逻辑搬迁，不改行为）。
- 验收：空闲画布页无周期性 5s 请求；生成完成后记录秒级出现；页面代码行数明显下降。

### 阶段 5 · 全站 UI 焕新（风格 A：精致暗黑 + 克制辉光）
逐页顺序：登录 → Dashboard → 项目创建 → 生成记录 → 设置 → 画布（画布仅换令牌与节点样式，不动布局逻辑）。

设计令牌（落地 `src/styles/theme.css`）：

| 令牌 | 值 |
|---|---|
| 背景层级 | #0A0A0C（画布底）/ #0D0D0F(页面) / #141417(侧栏) / 卡片渐变 180deg #1C1C21→#17171B |
| 主色 | #F5A623；主按钮渐变 135deg #F5A623→#E08D0C，投影 `0 4px 16px rgba(245,166,35,.3)` |
| 描边 | 常态 #2A2A30；活跃/选中 #F5A62366 + 辉光 `0 0 24px rgba(245,166,35,.14)`（仅进行中/选中态，克制原则） |
| 圆角 | 卡片 16px / 画布节点 14px / 按钮 10px / 小标签 6-7px（`--radius` 从 0.25rem 全面加大） |
| 状态色 | 生成中金色脉冲点；成功 #7ED887；失败沿用现有 destructive |
| 文字 | 页标题 800 字重；辅助文字 #6B6B72；小标签 9-11px |

- 附带修正：`index.html` 的 `lang="en"` 改 `lang="zh-CN"`，补 meta description 与 favicon。
- 验收：与已确认的 mockup（`.superpowers/brainstorm/1250-1783262470/content/style-a-detail.html`）逐页比对；暗色对比度满足可读性。

## 6. 工作流与部署

- 开发：本地克隆 → 本地验证 → push main。
- 部署（每阶段）：服务器 `git pull` → `docker compose -f docker-compose.production.yml build app` → 重启容器 → 冒烟验证（登录、开画布、生成一张图、Network 面板抽查）。
- 回滚：镜像按 git sha 打 tag，出问题运行上一 tag 即回滚。nginx 改动保留 `.bak` 并 `nginx -t` 后 reload。

## 7. 错误处理与风险

| 风险 | 应对 |
|---|---|
| memo 后节点不更新（props 引用问题） | 阶段 1 逐节点验证交互（选中、编辑、生成状态刷新） |
| 缩略图脚本处理存量图片失败 | 脚本幂等可重跑；前端缩略图 404 时 fallback 原图 |
| 孪生文件合并引入行为差异 | 合并前先 diff 产出差异清单；现有测试（*.test.ts）全部通过后再删旧文件 |
| TanStack Query 迁移改变时序 | 阶段 4 保留 60s 兜底轮询；分接口逐个迁移而非一次性替换 |
| UI 令牌改动影响画布可用性 | 画布页放最后；令牌变更后全页面截图比对 |
| 服务器部署失败 | 按 sha 回滚镜像；数据库无 schema 变更（本期不动 Prisma 模型，除非 episodeId 过滤需要索引——只加索引不改结构） |

## 8. 验收总表

1. 拖动画布节点，其余节点零重渲染（Profiler 证据）。
2. 生成记录接口 gzip 后 <200KB，空闲时无 5s 轮询。
3. 图片列表全部 WebP 缩略图，静态资源长缓存命中。
4. `motion`、`react-slick`、孪生文件从仓库消失，build 通过。
5. 生成完成后前端秒级刷新（socket 推送）。
6. 全站 6 页视觉与确认稿一致。
