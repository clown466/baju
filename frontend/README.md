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
