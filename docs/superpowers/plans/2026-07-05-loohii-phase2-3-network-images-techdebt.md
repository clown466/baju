# 鹿绘 AI 阶段 2+3（网络与图片 + 技术债清理）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 生产接口/静态资源启用 gzip 与长缓存，图片走 WebP 缩略图（新图落盘即生成 + 存量回填 + 前端按需请求），并清除孪生死文件与四个未使用依赖。

**Architecture:** nginx 只负责解注释 gzip；缓存与图片全部在 Express/Node 层解决（uploads 由 Express 路由直出）。缩略图采用「文件名约定 + 前端改写 URL + onError 回退原图」，不改任何 API 响应结构。技术债清理基于已验证事实：`canvasHelpers.ts` 零引用（死代码），`motion`/`framer-motion`/`react-slick`/`embla-carousel-react` 四包在 src 内零 import。

**Tech Stack:** Express 5、sharp（新增）、node:test via `npx tsx --test`、React 18 + Vite 6、Docker（服务器构建）、plink 远程操作。

## Global Constraints

- 仓库：`H:\claude项目\loohii`，分支 `main`。当前 HEAD：`1859b54`（tag `phase-1-done`）。
- 本地无 Docker（虚拟化禁用）：服务端行为在生产部署后验证；本地只做 `npm run build`、`npx tsx --test`、纯函数测试。
- **lockfile 纪律**：本地 `package-lock.json` 有无关改动。凡不改依赖的任务：绝不提交 `package-lock.json` 与 `.env.local`。凡改依赖的任务（Task 3、Task 8）：先 `git checkout -- package-lock.json` 恢复干净基线，再执行 npm install/uninstall，然后把 `package.json` + `package-lock.json` 一起提交（Dockerfile 用 `npm ci`，两者必须一致）。
- 服务器操作统一用（下文简称 `PLINK "…"`）：
  `plink -ssh -batch -hostkey "SHA256:oMogBHYLu9S5widJ1D2MopEELwkNTb0EPS7OYnIzbJI" root@157.254.234.105 -pw "KZczfxxh7XnPcnEK" "…"`
- 服务器部署方式是**裸 docker run**（不是 compose，compose 网络标签已损坏，禁止 `docker compose up`）。重建容器的标准命令见 Task 6 Step 3。
- 上传根目录：容器内 `/var/lib/loohii/uploads`（env `LOCAL_UPLOAD_ROOT`，卷 `loohii_uploads`，约 2.3GB）。
- 图片 URL 形态：`/api/uploads/public/<userId>/…/<name>.<png|jpg|jpeg|webp|gif>`，由 `server/src/routes/uploads.ts:41` 的正则路由直出，已带 `Cache-Control: public, max-age=31536000, immutable`。
- 缩略图命名约定（全局唯一真理）：`<原文件绝对路径>.thumb300.webp` 与 `<原文件绝对路径>.thumb1024.webp`（追加后缀，不替换扩展名）。URL 同理：原图 URL 直接追加 `.thumb300.webp`。
- 提交信息用 conventional commits；git 身份已配置（Hermes Agent）。

---

### Task 1: nginx 启用 gzip（纯服务器操作，无代码）

**Files:**
- 无仓库改动；修改服务器 `/etc/nginx/nginx.conf`（第 47-54 行区域，`gzip on;` 已开但 `gzip_types` 等被注释）

**Interfaces:**
- Produces: 生产环境对 JSON/JS/CSS 的 gzip 压缩（阶段 2 验收前提）

- [ ] **Step 1: 备份并解注释 gzip 配置**

```bash
PLINK "cp /etc/nginx/nginx.conf /etc/nginx/nginx.conf.bak-phase2 && sed -i 's|^\t# gzip_vary on;|\tgzip_vary on;|; s|^\t# gzip_proxied any;|\tgzip_proxied any;|; s|^\t# gzip_comp_level 6;|\tgzip_comp_level 6;|; s|^\t# gzip_buffers 16 8k;|\tgzip_buffers 16 8k;|; s|^\t# gzip_http_version 1.1;|\tgzip_http_version 1.1;|; s|^\t# gzip_types .*|\tgzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;|' /etc/nginx/nginx.conf && grep -n 'gzip' /etc/nginx/nginx.conf"
```

Expected: 6 行 gzip 指令均无 `#` 前缀。若 sed 未命中（缩进是空格不是 tab），先 `grep -n 'gzip' /etc/nginx/nginx.conf` 查看实际缩进后调整 sed 或直接用 `sed -i 's|# gzip_|gzip_|' 行号范围` 处理。

- [ ] **Step 2: 校验并 reload**

```bash
PLINK "nginx -t && systemctl reload nginx"
```

Expected: `syntax is ok` / `test is successful`。失败则 `cp /etc/nginx/nginx.conf.bak-phase2 /etc/nginx/nginx.conf` 回滚。

- [ ] **Step 3: 验证压缩生效**

```bash
curl -s -o /dev/null -w '%{size_download} bytes, encoding=%header{content-encoding}\n' -H 'Accept-Encoding: gzip' https://loohii.com/assets/index-e3c0SpkK.js
curl -s -o /dev/null -w 'encoding=%header{content-encoding}\n' -H 'Accept-Encoding: gzip' https://loohii.com/health
```

Expected: 两个请求都输出 `encoding=gzip`；JS 下载体积明显小于 449KB（约 100-150KB）。

- [ ] **Step 4: 在 progress ledger 记录**（无 git 提交，此任务改的是服务器）

---

### Task 2: Express 静态资源长缓存（/assets immutable，index.html no-cache）

**Files:**
- Modify: `server/src/http.ts:48-53`

**Interfaces:**
- Consumes: 现有 `createHttpApp`（http.ts:11），静态目录 `dist/`，Vite 产物在 `dist/assets/` 且文件名带 hash
- Produces: `/assets/*` 响应头 `Cache-Control: public, max-age=31536000, immutable`；`index.html` 响应 `Cache-Control: no-cache`

- [ ] **Step 1: 修改 http.ts**

将 http.ts 第 48-53 行：

```ts
  const staticDir = path.resolve(__dirname, "../../dist");
  app.use(express.static(staticDir));
  app.use((req, res, next) => {
    if (req.path.startsWith("/api") || req.path.startsWith("/socket.io")) return next();
    res.sendFile(path.join(staticDir, "index.html"));
  });
```

改为：

```ts
  const staticDir = path.resolve(__dirname, "../../dist");
  app.use("/assets", express.static(path.join(staticDir, "assets"), { immutable: true, maxAge: "365d" }));
  app.use(
    express.static(staticDir, {
      setHeaders: (res, filePath) => {
        if (filePath.endsWith("index.html")) res.setHeader("Cache-Control", "no-cache");
      },
    }),
  );
  app.use((req, res, next) => {
    if (req.path.startsWith("/api") || req.path.startsWith("/socket.io")) return next();
    res.setHeader("Cache-Control", "no-cache");
    res.sendFile(path.join(staticDir, "index.html"));
  });
```

- [ ] **Step 2: 本地校验（类型与现有测试）**

```bash
cd "H:\claude项目\loohii" && npx tsc --noEmit -p tsconfig.json 2>&1 | head -5; npx tsx --test server/src/routes/workflows.test.ts 2>&1 | tail -3
```

Expected: 无新增类型错误（若项目 tsconfig 本身报既有错误，确认与本改动无关即可）；现有测试全过。真实响应头在 Task 6 部署后用 curl 验证。

- [ ] **Step 3: Commit**

```bash
cd "H:\claude项目\loohii" && git add server/src/http.ts && git commit -m "perf(server): immutable cache for hashed /assets, no-cache for index.html"
```

---

### Task 3: sharp 缩略图生成模块（TDD）+ 接入 4 个图片落盘点

**Files:**
- Create: `server/src/lib/imageThumbnails.ts`
- Test: `server/src/lib/imageThumbnails.test.ts`
- Modify: `server/src/routes/uploads.ts`（local-image :148 后、local-file :181 后）
- Modify: `server/src/routes/workflows.ts`（`persistGeneratedImageBuffer` :9989 后、asset reference 落盘 :10197 后——行号可能漂移，以 `await writeFile(resolvedPath, buffer)` 且写入的是图片为准；**视频落盘点（~:10950）不接**）
- Modify: `package.json` + `package-lock.json`（新增 sharp）

**Interfaces:**
- Produces:
  - `thumbnailPathFor(filePath: string, width: 300 | 1024): string` — 返回 `${filePath}.thumb${width}.webp`
  - `generateImageThumbnails(filePath: string): Promise<void>` — 为一个已落盘图片生成两档 WebP 缩略图；非图片扩展名直接返回；失败抛错（调用方 catch）
  - Task 4 的前端 URL 约定、Task 5 的回填脚本都依赖 `.thumb300.webp` / `.thumb1024.webp` 命名

- [ ] **Step 1: 恢复 lockfile 基线并安装 sharp**

```bash
cd "H:\claude项目\loohii" && git checkout -- package-lock.json && npm install sharp@^0.34 && git diff --stat package.json package-lock.json
```

Expected: package.json dependencies 新增 `"sharp"`；lockfile 仅含 sharp 相关新增。

- [ ] **Step 2: 写失败测试**

`server/src/lib/imageThumbnails.test.ts`：

```ts
import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, rm, stat } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import sharp from "sharp";
import { generateImageThumbnails, thumbnailPathFor } from "./imageThumbnails";

test("thumbnailPathFor appends suffix without replacing extension", () => {
  assert.equal(thumbnailPathFor("/a/b/c.png", 300), "/a/b/c.png.thumb300.webp");
  assert.equal(thumbnailPathFor("/a/b/c.jpg", 1024), "/a/b/c.jpg.thumb1024.webp");
});

test("generateImageThumbnails creates both webp thumbnails", async () => {
  const dir = await mkdtemp(path.join(tmpdir(), "thumbs-"));
  try {
    const src = path.join(dir, "source.png");
    await sharp({ create: { width: 2000, height: 1200, channels: 3, background: { r: 200, g: 100, b: 50 } } })
      .png()
      .toFile(src);
    await generateImageThumbnails(src);
    const t300 = await sharp(thumbnailPathFor(src, 300)).metadata();
    const t1024 = await sharp(thumbnailPathFor(src, 1024)).metadata();
    assert.equal(t300.format, "webp");
    assert.equal(t300.width, 300);
    assert.equal(t1024.format, "webp");
    assert.equal(t1024.width, 1024);
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
});

test("generateImageThumbnails does not enlarge small images", async () => {
  const dir = await mkdtemp(path.join(tmpdir(), "thumbs-"));
  try {
    const src = path.join(dir, "small.png");
    await sharp({ create: { width: 200, height: 150, channels: 3, background: { r: 1, g: 2, b: 3 } } })
      .png()
      .toFile(src);
    await generateImageThumbnails(src);
    const t300 = await sharp(thumbnailPathFor(src, 300)).metadata();
    assert.equal(t300.width, 200);
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
});

test("generateImageThumbnails skips non-image extensions", async () => {
  const dir = await mkdtemp(path.join(tmpdir(), "thumbs-"));
  try {
    const src = path.join(dir, "video.mp4");
    await generateImageThumbnails(src); // 不应抛错、不应产文件
    await assert.rejects(stat(thumbnailPathFor(src, 300)));
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
});
```

- [ ] **Step 3: 跑测试确认失败**

```bash
cd "H:\claude项目\loohii" && npx tsx --test server/src/lib/imageThumbnails.test.ts
```

Expected: FAIL，`Cannot find module './imageThumbnails'`。

- [ ] **Step 4: 实现 imageThumbnails.ts**

```ts
import path from "node:path";
import sharp from "sharp";

export const THUMBNAIL_WIDTHS = [300, 1024] as const;
export type ThumbnailWidth = (typeof THUMBNAIL_WIDTHS)[number];

const IMAGE_EXTENSION_RE = /\.(png|jpe?g|webp|gif)$/i;

export function thumbnailPathFor(filePath: string, width: ThumbnailWidth): string {
  return `${filePath}.thumb${width}.webp`;
}

export function isThumbnailableImagePath(filePath: string): boolean {
  return IMAGE_EXTENSION_RE.test(filePath) && !/\.thumb(300|1024)\.webp$/i.test(filePath);
}

export async function generateImageThumbnails(filePath: string): Promise<void> {
  if (!isThumbnailableImagePath(filePath)) return;
  for (const width of THUMBNAIL_WIDTHS) {
    await sharp(filePath, { animated: false })
      .rotate()
      .resize({ width, withoutEnlargement: true })
      .webp({ quality: 78 })
      .toFile(thumbnailPathFor(filePath, width));
  }
}

export function logThumbnailError(filePath: string, error: unknown): void {
  const message = error instanceof Error ? error.message : String(error);
  console.warn(`[thumbnails] failed for ${path.basename(filePath)}: ${message}`);
}
```

- [ ] **Step 5: 跑测试确认通过**

```bash
cd "H:\claude项目\loohii" && npx tsx --test server/src/lib/imageThumbnails.test.ts
```

Expected: 4/4 PASS。

- [ ] **Step 6: 接入 4 个落盘点（fire-and-forget，不阻塞响应）**

在 `server/src/routes/uploads.ts` 顶部加：

```ts
import { generateImageThumbnails, logThumbnailError } from "../lib/imageThumbnails";
```

在 `/local-image` 的 `await writeFile(resolvedPath, parsed.buffer);`（:148）之后加：

```ts
    void generateImageThumbnails(resolvedPath).catch((err) => logThumbnailError(resolvedPath, err));
```

在 `/local-file` 的 `await writeFile(resolvedPath, buffer);`（:181）之后加（仅图片才会真正生成，模块内部已按扩展名过滤）：

```ts
    void generateImageThumbnails(resolvedPath).catch((err) => logThumbnailError(resolvedPath, err));
```

在 `server/src/routes/workflows.ts` 顶部加同样 import（注意相对路径 `../lib/imageThumbnails`），并在以下两处 `await writeFile(resolvedPath, buffer);` 之后加同一行：
1. `persistGeneratedImageBuffer`（~:9989，生成图落盘）
2. asset reference 图落盘（~:10197，`Invalid reference image path` 校验所在函数）

**不要**接视频落盘函数（`超过 500MB` 校验、`convertGeneratedVideoToBrowserWebm` 所在的那个）。

- [ ] **Step 7: 全量测试 + build**

```bash
cd "H:\claude项目\loohii" && npx tsx --test server/src/lib/imageThumbnails.test.ts server/src/routes/workflows.test.ts && npm run build 2>&1 | tail -3
```

Expected: 全部 PASS；build 成功。

- [ ] **Step 8: Commit**

```bash
cd "H:\claude项目\loohii" && git add package.json package-lock.json server/src/lib/imageThumbnails.ts server/src/lib/imageThumbnails.test.ts server/src/routes/uploads.ts server/src/routes/workflows.ts && git commit -m "feat(server): generate 300/1024 webp thumbnails on image write (sharp)"
```

---

### Task 4: 前端 thumbUrl（TDD）+ ThumbImage 组件 + 应用到列表与节点

**Files:**
- Create: `src/app/lib/thumbUrl.ts`
- Test: `src/app/lib/thumbUrl.test.ts`
- Create: `src/app/components/ThumbImage.tsx`
- Modify（thumb300 小缩略场景）: `src/app/features/canvas/components/AssetMiniList.tsx:172`、`src/app/features/canvas/components/CharacterPropPickerPanel.tsx:93`、`src/app/features/canvas/components/ClipStoryboardList.tsx:611`、`src/app/pages/DashboardPage.tsx:126`、`src/app/pages/ProjectRecordsPage.tsx`（记录列表 img）、`src/app/pages/ProjectCanvasPage.tsx:5666/5697/5750/6105/6173`（生成记录列表）
- Modify（thumb1024 节点预览场景）: `src/app/features/canvas/nodes/CharacterNode.tsx:232/257/395`、`GenerationNode.tsx:782/832/1065`、`ImageInputNode.tsx:175`、`SceneNode.tsx:63/83`
- 行号自阶段 1 起可能漂移 ±10 行，以 `<img` + src 表达式为准；`ProjectCanvasPage.tsx:6753` 全屏预览保持原图，**不改**

**Interfaces:**
- Consumes: Task 3 的命名约定 `.thumb300.webp` / `.thumb1024.webp`
- Produces:
  - `thumbUrl(url: string | null | undefined, width: 300 | 1024): string` — 仅本站 uploads 图片 URL 追加缩略后缀，其余原样返回
  - `ThumbImage`（React 组件）：props = `React.ImgHTMLAttributes<HTMLImageElement> & { src: string; thumbWidth?: 300 | 1024 }`，缩略图 404 时自动回退原图

- [ ] **Step 1: 写失败测试** `src/app/lib/thumbUrl.test.ts`：

```ts
import test from "node:test";
import assert from "node:assert/strict";
import { thumbUrl } from "./thumbUrl";

test("appends thumb suffix for local upload images", () => {
  assert.equal(
    thumbUrl("https://loohii.com/api/uploads/public/u1/a.png", 300),
    "https://loohii.com/api/uploads/public/u1/a.png.thumb300.webp",
  );
  assert.equal(
    thumbUrl("/api/uploads/public/u1/gen/b.jpg", 1024),
    "/api/uploads/public/u1/gen/b.jpg.thumb1024.webp",
  );
});

test("returns external and non-image urls unchanged", () => {
  assert.equal(thumbUrl("https://cdn.example.com/x.png", 300), "https://cdn.example.com/x.png");
  assert.equal(thumbUrl("/api/uploads/public/u1/v.mp4", 300), "/api/uploads/public/u1/v.mp4");
});

test("handles empty and already-thumbnailed urls", () => {
  assert.equal(thumbUrl(undefined, 300), "");
  assert.equal(thumbUrl(null, 300), "");
  assert.equal(
    thumbUrl("/api/uploads/public/u1/a.png.thumb300.webp", 300),
    "/api/uploads/public/u1/a.png.thumb300.webp",
  );
});

test("ignores data and blob urls", () => {
  assert.equal(thumbUrl("data:image/png;base64,AAAA", 300), "data:image/png;base64,AAAA");
  assert.equal(thumbUrl("blob:https://loohii.com/xyz", 300), "blob:https://loohii.com/xyz");
});
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd "H:\claude项目\loohii" && npx tsx --test src/app/lib/thumbUrl.test.ts
```

Expected: FAIL（模块不存在）。

- [ ] **Step 3: 实现** `src/app/lib/thumbUrl.ts`：

```ts
const LOCAL_UPLOAD_IMAGE_RE = /\/api\/uploads\/public\/.+\.(png|jpe?g|webp|gif)$/i;

export function thumbUrl(url: string | null | undefined, width: 300 | 1024): string {
  if (!url) return "";
  if (/\.thumb(300|1024)\.webp$/i.test(url)) return url;
  if (url.startsWith("data:") || url.startsWith("blob:")) return url;
  if (!LOCAL_UPLOAD_IMAGE_RE.test(url)) return url;
  return `${url}.thumb${width}.webp`;
}
```

- [ ] **Step 4: 跑测试确认通过**（同 Step 2 命令）Expected: 4/4 PASS。

- [ ] **Step 5: 实现 ThumbImage 组件** `src/app/components/ThumbImage.tsx`：

```tsx
import React, { useState } from "react";
import { thumbUrl } from "../lib/thumbUrl";

type ThumbImageProps = React.ImgHTMLAttributes<HTMLImageElement> & {
  src: string;
  thumbWidth?: 300 | 1024;
};

export function ThumbImage({ src, thumbWidth = 300, onError, ...rest }: ThumbImageProps) {
  const [failedThumbSrc, setFailedThumbSrc] = useState<string | null>(null);
  const thumb = thumbUrl(src, thumbWidth);
  const resolved = failedThumbSrc === src ? src : thumb;
  return (
    <img
      src={resolved}
      loading="lazy"
      decoding="async"
      {...rest}
      onError={(event) => {
        if (resolved !== src) {
          setFailedThumbSrc(src);
          return;
        }
        onError?.(event);
      }}
    />
  );
}
```

- [ ] **Step 6: 替换应用点**

对 Files 列表中的每个 `<img …>`：若 src 可能是本站 uploads URL（生成结果图、上传参考图、封面），替换为 `<ThumbImage src={…} thumbWidth={300 或 1024} …其余属性原样 />` 并删除原有的 `loading`/`decoding` 属性（组件已内置）。判断标准：
- 小列表缩略（≤200px 显示宽度）→ `thumbWidth={300}`
- 画布节点内预览图 → `thumbWidth={1024}`
- src 明确是外部 CDN、data URL、静态资源（如 logo、头像 dicebear）→ **不换**
- 全屏/放大预览（ProjectCanvasPage:6753、各节点点开大图）→ **不换**，保持原图

- [ ] **Step 7: build + 全量测试**

```bash
cd "H:\claude项目\loohii" && npx tsx --test src/app/lib/thumbUrl.test.ts src/app/features/canvas/generationRecordsFingerprint.test.ts && npm run build 2>&1 | tail -3
```

Expected: 测试全过、build 成功。

- [ ] **Step 8: Commit**

```bash
cd "H:\claude项目\loohii" && git add src/app/lib/thumbUrl.ts src/app/lib/thumbUrl.test.ts src/app/components/ThumbImage.tsx && git add -u src/app && git commit -m "perf(web): request webp thumbnails for list and node images with original fallback"
```

---

### Task 5: 存量图片缩略图回填脚本（幂等）

**Files:**
- Create: `scripts/backfill-thumbnails.ts`

**Interfaces:**
- Consumes: `generateImageThumbnails` / `thumbnailPathFor` / `isThumbnailableImagePath`（Task 3，从 `../server/src/lib/imageThumbnails` import）
- Produces: 可在容器内以 `npx tsx scripts/backfill-thumbnails.ts` 重复运行的脚本（Task 6 部署时执行）

- [ ] **Step 1: 实现脚本**

```ts
import { readdir, stat } from "node:fs/promises";
import path from "node:path";
import {
  generateImageThumbnails,
  isThumbnailableImagePath,
  thumbnailPathFor,
  THUMBNAIL_WIDTHS,
} from "../server/src/lib/imageThumbnails";

const ROOT = process.env.LOCAL_UPLOAD_ROOT || "/var/lib/loohii/uploads";

async function* walk(dir: string): AsyncGenerator<string> {
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) yield* walk(full);
    else if (entry.isFile()) yield full;
  }
}

async function needsThumbnails(filePath: string): Promise<boolean> {
  for (const width of THUMBNAIL_WIDTHS) {
    try {
      await stat(thumbnailPathFor(filePath, width));
    } catch {
      return true;
    }
  }
  return false;
}

async function main() {
  let done = 0;
  let skipped = 0;
  let failed = 0;
  for await (const file of walk(ROOT)) {
    if (!isThumbnailableImagePath(file)) continue;
    if (!(await needsThumbnails(file))) {
      skipped += 1;
      continue;
    }
    try {
      await generateImageThumbnails(file);
      done += 1;
      if (done % 100 === 0) console.log(`progress: ${done} generated`);
    } catch (error) {
      failed += 1;
      console.warn(`failed: ${file}: ${error instanceof Error ? error.message : String(error)}`);
    }
  }
  console.log(`backfill complete: generated=${done} skipped=${skipped} failed=${failed}`);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
```

- [ ] **Step 2: 本地冒烟（用临时目录验证幂等）**

```bash
cd "H:\claude项目\loohii" && mkdir -p /tmp/thumbs-smoke && npx tsx -e "import sharp from 'sharp'; await sharp({create:{width:800,height:600,channels:3,background:{r:9,g:9,b:9}}}).png().toFile('/tmp/thumbs-smoke/x.png')" && LOCAL_UPLOAD_ROOT=/tmp/thumbs-smoke npx tsx scripts/backfill-thumbnails.ts && LOCAL_UPLOAD_ROOT=/tmp/thumbs-smoke npx tsx scripts/backfill-thumbnails.ts && ls /tmp/thumbs-smoke
```

Expected: 第一次 `generated=1`，第二次 `generated=0 skipped=1`；目录含 `x.png`、`x.png.thumb300.webp`、`x.png.thumb1024.webp`。（Git Bash 下 /tmp 可用；若路径问题改用 `$TEMP` 子目录。）

- [ ] **Step 3: Commit**

```bash
cd "H:\claude项目\loohii" && git add scripts/backfill-thumbnails.ts && git commit -m "feat(scripts): idempotent thumbnail backfill for existing uploads"
```

---

### Task 6: 部署阶段 2 并验收

**Files:** 无代码改动；操作生产服务器

**Interfaces:**
- Consumes: Task 1-5 全部产物

- [ ] **Step 1: 推送**

```bash
cd "H:\claude项目\loohii" && git push origin main && git rev-parse --short HEAD
```

Expected: push 成功，记下 `<sha>`。

- [ ] **Step 2: 服务器拉取并构建（按 SHA 打 tag）**

```bash
PLINK "cd /projects/loohii && git pull && docker build -f Dockerfile.loohii -t loohii-app:latest -t loohii-app:<sha> . 2>&1 | tail -3 && docker images | grep loohii-app | head -3"
```

Expected: build 成功（sharp 在 alpine 上用预编译 musl 二进制，`npm ci` 直接装好；若报 sharp 安装错误，在 Dockerfile `apk add` 行补 `vips-dev` 后重试并把该 Dockerfile 改动提交回仓库）。

- [ ] **Step 3: 重建容器（标准裸 docker run 程序）**

```bash
PLINK "docker stop loohii-app && docker rm loohii-app && docker run -d --name loohii-app --restart unless-stopped --network loohii_default --network-alias app -p 127.0.0.1:3001:3001 --env-file /root/loohii-repeat-to-157-20260629-095447/meta/loohii-app.env -v loohii_uploads:/var/lib/loohii/uploads loohii-app:<sha> && sleep 8 && curl -s -o /dev/null -w 'HTTP=%{http_code}\n' http://127.0.0.1:3001 && docker logs loohii-app --tail 5 2>&1"
```

Expected: `HTTP=200`，日志出现 `Loohii backend listening`。回滚：同命令把镜像换成上一个 sha tag（阶段 1 是 `loohii-app:1859b54`）。

- [ ] **Step 4: 执行存量回填（后台 + 可重跑）**

```bash
PLINK "docker exec -d loohii-app sh -c 'npx tsx scripts/backfill-thumbnails.ts > /tmp/backfill.log 2>&1'"
```

等待数分钟后：

```bash
PLINK "docker exec loohii-app tail -3 /tmp/backfill.log && docker exec loohii-app sh -c 'find /var/lib/loohii/uploads -name \"*.thumb300.webp\" | wc -l'"
```

Expected: `backfill complete: generated=N skipped=M failed=K`（K 应接近 0）；thumb 文件数 > 0。未完成就再等，不要重复启动。

- [ ] **Step 5: 线上验收**

```bash
curl -s -o /dev/null -w 'cache=%header{cache-control} encoding=%header{content-encoding}\n' -H 'Accept-Encoding: gzip' https://loohii.com/assets/$(curl -s https://loohii.com | grep -o 'assets/index-[^"]*\.js' | head -1 | cut -d/ -f2)
curl -s -o /dev/null -w 'thumb http=%{http_code} type=%header{content-type} size=%{size_download}\n' "https://loohii.com/api/uploads/public/<任选一个已知图片key>.thumb300.webp"
```

Expected: assets 响应 `cache=public, max-age=31536000, immutable` 且 `encoding=gzip`；thumb 请求 200、`image/webp`、体积远小于原图。浏览器人工检查：画布节点与生成记录列表的图片请求为 `.thumb*.webp`（Network 面板），缩略图缺失的图正常回退原图。

- [ ] **Step 6: 打 tag**

```bash
cd "H:\claude项目\loohii" && git tag phase-2-done && git push origin phase-2-done
```

---

### Task 7: 删除孪生死文件 canvasHelpers.ts

**Files:**
- Delete: `src/app/features/canvas/canvasHelpers.ts`（6556 行，已确认 0 个文件 import；canvasUtils.tsx 是其超集且是唯一被引用者）

**Interfaces:**
- Consumes: 无
- Produces: 无（纯删除）

- [ ] **Step 1: 复核零引用（含动态 import 与字符串引用）**

```bash
cd "H:\claude项目\loohii" && grep -rn "canvasHelpers" --include="*.ts" --include="*.tsx" --include="*.json" src server scripts vite.config.ts 2>/dev/null | grep -v "canvasHelpers.ts:"
```

Expected: 无输出。若有任何引用，停止并报告 BLOCKED。

- [ ] **Step 2: 删除并构建**

```bash
cd "H:\claude项目\loohii" && git rm src/app/features/canvas/canvasHelpers.ts && npm run build 2>&1 | tail -3 && npx tsx --test src/app/features/canvas/canvasNodeChanges.test.ts src/app/features/canvas/canvasPromptText.test.ts src/app/features/canvas/canvasLoadViewport.test.ts 2>&1 | tail -3
```

Expected: build 成功，canvas 相关既有测试全过。

- [ ] **Step 3: Commit**

```bash
cd "H:\claude项目\loohii" && git commit -m "chore: remove dead twin file canvasHelpers.ts (superseded by canvasUtils)"
```

---

### Task 8: 依赖去重（删除 4 个零引用包）

**Files:**
- Modify: `package.json` + `package-lock.json`（移除 `motion`、`framer-motion`、`react-slick`、`embla-carousel-react`）

**Interfaces:**
- Consumes: 无
- Produces: 更小的 node_modules 与安装面

前置事实：4 包在 src/ 内均无 import（已初步验证），设计文档原定「保留 framer-motion 与 embla」是基于误判，实际全部未使用。

- [ ] **Step 1: 逐包复核零引用（含变体 import 形式与 CSS）**

```bash
cd "H:\claude项目\loohii" && grep -rn "from ['\"]motion\|from ['\"]framer-motion\|react-slick\|slick-carousel\|embla-carousel\|require(['\"]motion" --include="*.ts" --include="*.tsx" --include="*.css" src server 2>/dev/null
```

Expected: 无输出（注意 `motion/react` 形式也被 `from ['\"]motion` 前缀覆盖）。任何命中 → 该包保留，仅删其余，并在报告中说明。

- [ ] **Step 2: 恢复 lockfile 基线并卸载**

```bash
cd "H:\claude项目\loohii" && git checkout -- package-lock.json && npm uninstall motion framer-motion react-slick embla-carousel-react && git diff --stat package.json package-lock.json
```

Expected: package.json 少 4 行依赖；lockfile 相应缩减。

- [ ] **Step 3: build + 全站既有测试**

```bash
cd "H:\claude项目\loohii" && npm run build 2>&1 | tail -5 && npx tsx --test src/app/features/canvas/generationRecordsFingerprint.test.ts src/app/lib/thumbUrl.test.ts 2>&1 | tail -3
```

Expected: build 成功（记录 bundle 体积对比可写入报告）；测试过。

- [ ] **Step 4: Commit**

```bash
cd "H:\claude项目\loohii" && git add package.json package-lock.json && git commit -m "chore: drop unused deps (motion, framer-motion, react-slick, embla-carousel-react)"
```

---

### Task 9: MUI 使用量报告（只读分析，不迁移）

**Files:**
- Create: `docs/mui-usage-report.md`（loohii 仓库内）

**Interfaces:**
- Produces: 后续「MUI → Radix」决策依据

- [ ] **Step 1: 统计**

```bash
cd "H:\claude项目\loohii" && grep -rn "from ['\"]@mui" --include="*.tsx" --include="*.ts" src | sed 's/:.*from/ ->/' | sort > /tmp/mui-imports.txt && grep -rl "from ['\"]@mui" --include="*.tsx" --include="*.ts" src | wc -l && grep -rhn "from ['\"]@mui/material['\"]" --include="*.tsx" src -A0 | grep -o '{[^}]*}' | tr ',' '\n' | tr -d '{} ' | sort | uniq -c | sort -rn | head -30
```

- [ ] **Step 2: 写报告** `docs/mui-usage-report.md`，包含：引用文件总数、按组件名的使用频次表（上一步输出整理成 markdown 表格）、Top5 重度使用文件、与 Radix 等价组件对照列（有 Radix 对应包的标 ✔）、结论段（迁移工作量粗估：高/中/低）。数据必须来自 Step 1 实际输出，不得编造。

- [ ] **Step 3: Commit**

```bash
cd "H:\claude项目\loohii" && git add docs/mui-usage-report.md && git commit -m "docs: MUI component usage report for future Radix migration decision"
```

---

### Task 10: 部署阶段 3 并验收

**Files:** 无代码改动；操作生产服务器

**Interfaces:**
- Consumes: Task 7-9 的 commits

- [ ] **Step 1: 推送并记录 SHA**

```bash
cd "H:\claude项目\loohii" && git push origin main && git rev-parse --short HEAD
```

- [ ] **Step 2: 服务器构建 + 重建容器**（同 Task 6 Step 2-3，镜像 tag 换成新 `<sha>`）

Expected: `HTTP=200`、日志正常。

- [ ] **Step 3: 验收**

```bash
curl -s -o /dev/null -w 'home=%{http_code}\n' https://loohii.com && curl -s https://loohii.com/health
```

浏览器冒烟：登录、打开画布、生成记录列表、设置页各点一遍无白屏/报错（4 个被删包本就无引用，重点是确认 build 产物完整）。对比 build 输出：node_modules 安装量与 bundle 无回归。

- [ ] **Step 4: 打 tag**

```bash
cd "H:\claude项目\loohii" && git tag phase-3-done && git push origin phase-3-done
```
