# TikTok 剧集下载器（桌面版）设计文档

日期：2026-07-05
状态：已确认

## 背景

已在本机手动验证完整流程：调试版 Chrome + Playwright 拦截 TikTok `api/post/item_list` 响应采集作者全部视频（1579 个，突破未登录 API 仅返回 6 个的限制），按剧名分组、按上传时间编集号，yt-dlp 3 线程批量下载成功。现将该流程产品化为可复用的桌面程序。

## 目标

- 输入任意 TikTok 作者主页链接（或 @账号、或单个视频链接），采集全部视频
- 按剧名分文件夹、按上传时间顺序命名 `第NN集.mp4`
- 用户可勾选要下载的剧、自选下载根目录
- 登录一次永久复用（专用 Chrome 配置目录），无需手动导出 cookies

## 技术选型

- **Python 3 + tkinter**（界面，标准库自带）
- **Playwright (Python)** 控制本机 Chrome（`channel="chrome"` + 独立 `--user-data-dir`）
- **yt-dlp** 子进程下载
- 选择理由：脚本语言易维护升级；yt-dlp/Playwright 均为 Python 原生生态；后续可用 PyInstaller 打包 exe

## 界面（单窗口）

```
账号/视频链接: [___________________] [采集]
下载目录:     [默认: 程序目录\下载] [浏览...]
剧集列表:  ☑ 剧名A  59集
           ☑ 剧名B  20集   [全选] [全不选]
[开始下载] [停止]
进度条  已完成/总数  失败数
日志滚动区
```

## 程序结构

```
tiktok_downloader/
├── app.py           # 入口 + tkinter 界面（主线程）
├── collector.py     # Playwright 启动专用 Chrome，滚动采集 → [(id, createTime, desc)]
├── organizer.py     # 标题清洗、按剧名分组、按时间编集号
├── downloader.py    # yt-dlp 多线程下载（3并发）、进度回调、失败重试
├── chrome_profile/  # 专用 Chrome 用户数据目录（登录态持久化）
└── requirements.txt # playwright, yt-dlp
```

## 关键流程

### 采集（collector.py）
1. Playwright `launch_persistent_context`（channel=chrome，user_data_dir=chrome_profile，headless=False）
2. 注册响应监听：URL 匹配 `api/post/item_list` → 解析 JSON `itemList`，收集 `id / desc / createTime`，记录 `hasMore`
3. 打开作者页，循环 `window.scrollTo(0, bottom)`，直到 `hasMore=false` 或连续 20 轮无新增（上限 500 轮）
4. DOM 中 `a[href*="/video/"]` 作为兜底补充
5. 输入为单视频链接时跳过采集，直接构造单条记录
6. 登录墙检测：滚动 30 秒仍 0 条且页面含登录组件 → 回调界面弹提示"请在浏览器中登录后重试"

### 分组编集（organizer.py）
- 剧名 = desc 去掉 `#` 起的话题标签、替换 Windows 非法字符 `\/:*?"<>|` 为 `_`、压缩空白、截断 80 字符；空标题归"未分类"
- 同剧按 createTime 升序编号 `第01集.mp4`（≥100 集时用三位数）

### 下载（downloader.py）
- ThreadPoolExecutor 3 并发，每任务：`yt-dlp --cookies <线程独立副本> -o <目录>/<剧名>/第NN集.%(ext)s <url>`
- cookies 从 chrome_profile 导出为 Netscape 格式，**每线程独立文件副本**（规避 yt-dlp 并发回写同一 cookies 文件的竞态，本次实测踩过）
- 目标文件已存在 → 跳过（断点续传）
- 单集失败 yt-dlp 自带 retries 5；全部结束后对失败清单自动串行重试一轮；仍失败的列入界面"失败"计数与日志
- 停止按钮：置停止标志，不再派发新任务，在途任务完成后停

### 界面线程模型
- 采集、下载均在后台线程；通过 `queue.Queue` + `root.after` 轮询向界面推送进度/日志，主线程不阻塞

## 错误处理

| 情况 | 处理 |
|---|---|
| 本机未装 Chrome | 弹窗提示并允许手动选择 chrome.exe 路径（保存到配置） |
| 未登录/登录失效 | 弹提示引导在专用 Chrome 里登录，点确定后重试采集 |
| 网络/单集失败 | yt-dlp 重试 5 次 + 结束后整体补试一轮，最终失败记 failed.txt |
| 非法链接输入 | 校验必须匹配 tiktok.com 作者页或视频 URL 或 @handle，否则提示 |

## 测试

- organizer 纯函数（清洗、分组、编号）：pytest 单元测试
- collector/downloader：用本次已验证的 @aidramalabs_anime2 数据做小规模手动验收（采集数量 > 6 即证明登录态生效；下载 1 部短剧验证目录/命名/跳过逻辑）

## 不做的事（YAGNI）

- 不支持播放列表链接、其他平台
- 不做视频转码/合并
- 暂不打包 exe（后续需要时用 PyInstaller 单独做）
