# TikTok 剧集下载器（桌面版）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 单窗口桌面程序：输入 TikTok 作者主页/单视频链接，采集全部视频，按剧名分文件夹、按时间编集号，勾选后批量下载。

**Architecture:** tkinter 主线程界面 + 后台线程跑采集/下载，queue 推送进度。采集用 Playwright 启动专用 Chrome（persistent context）拦截 `api/post/item_list` 响应；下载用 yt-dlp 子进程 3 并发，每线程独立 cookies 副本。

**Tech Stack:** Python 3.14, tkinter (标准库), playwright (pip), yt-dlp (已装), pytest

**Spec:** `docs/superpowers/specs/2026-07-05-tiktok-downloader-gui-design.md`

## Global Constraints

- 项目目录：`H:\claude项目\tiktok_downloader\`
- Windows 平台；文件名非法字符 `\/:*?"<>|` 替换为 `_`
- 剧名截断 80 字符；空标题归 `未分类`
- 集号：同剧 <100 集用 `第01集`，≥100 集用 `第001集`；按 createTime 升序
- 下载并发 3；yt-dlp 参数含 `--retries 5`；已存在文件跳过
- 所有源文件 UTF-8 编码
- 测试命令一律 `cd H:/claude项目/tiktok_downloader && python -m pytest`

---

### Task 1: 项目脚手架 + organizer.clean_series / parse_input

**Files:**
- Create: `tiktok_downloader/organizer.py`
- Create: `tiktok_downloader/requirements.txt`
- Test: `tiktok_downloader/tests/test_organizer.py`

**Interfaces:**
- Produces: `clean_series(desc: str) -> str`（剧名清洗）
- Produces: `parse_input(text: str) -> tuple[str, str]`，返回 `("user", "https://www.tiktok.com/@handle")` 或 `("video", "<原视频URL>")`；非法输入抛 `ValueError`
- Produces: `VideoItem` dataclass：`id: str, create_time: int, desc: str`

- [ ] **Step 1: 建目录与依赖文件**

```bash
mkdir -p "H:/claude项目/tiktok_downloader/tests"
```

`tiktok_downloader/requirements.txt`:
```
playwright
yt-dlp
pytest
```

- [ ] **Step 2: 写失败测试**

`tiktok_downloader/tests/test_organizer.py`:
```python
import pytest
from organizer import clean_series, parse_input


def test_clean_series_strips_hashtags():
    assert clean_series("Frost Oath #fyp #anime") == "Frost Oath"

def test_clean_series_replaces_illegal_chars():
    assert clean_series('Blood: Rise? "Kiwi"') == "Blood_ Rise_ _Kiwi_"

def test_clean_series_empty_becomes_unclassified():
    assert clean_series("") == "未分类"
    assert clean_series("#onlytags #fyp") == "未分类"

def test_clean_series_truncates_to_80():
    assert len(clean_series("x" * 200)) == 80

def test_clean_series_collapses_whitespace_and_trims_dots():
    assert clean_series("  A   B .") == "A B"

def test_parse_input_handle():
    assert parse_input("@somebody") == ("user", "https://www.tiktok.com/@somebody")

def test_parse_input_profile_url():
    assert parse_input("https://www.tiktok.com/@abc_1?lang=en") == ("user", "https://www.tiktok.com/@abc_1")

def test_parse_input_video_url():
    kind, url = parse_input("https://www.tiktok.com/@abc/video/123456?is_copy=1")
    assert kind == "video" and url == "https://www.tiktok.com/@abc/video/123456"

def test_parse_input_invalid_raises():
    with pytest.raises(ValueError):
        parse_input("https://example.com/foo")
```

- [ ] **Step 3: 运行确认失败**

Run: `cd H:/claude项目/tiktok_downloader && python -m pytest tests/test_organizer.py -v`
Expected: FAIL（`ModuleNotFoundError: organizer`）。若 pytest 未装：`pip install pytest`。需要 `tests/../organizer.py` 可导入，在项目根建 `conftest.py`：

```python
# tiktok_downloader/conftest.py
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
```

- [ ] **Step 4: 最小实现**

`tiktok_downloader/organizer.py`:
```python
import re
from dataclasses import dataclass


@dataclass
class VideoItem:
    id: str
    create_time: int
    desc: str


def clean_series(desc: str) -> str:
    name = re.sub(r"#.*", "", desc or "").strip()
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    name = re.sub(r"\s+", " ", name).strip(" ._")
    return name[:80].strip(" ._") or "未分类"


def parse_input(text: str) -> tuple[str, str]:
    text = (text or "").strip()
    m = re.match(r"^@([\w.\-]+)$", text)
    if m:
        return ("user", f"https://www.tiktok.com/@{m.group(1)}")
    m = re.match(r"^https?://(?:www\.)?tiktok\.com/(@[\w.\-]+)/video/(\d+)", text)
    if m:
        return ("video", f"https://www.tiktok.com/{m.group(1)}/video/{m.group(2)}")
    m = re.match(r"^https?://(?:www\.)?tiktok\.com/(@[\w.\-]+)/?(?:\?.*)?$", text)
    if m:
        return ("user", f"https://www.tiktok.com/{m.group(1)}")
    raise ValueError(f"无法识别的链接: {text}")
```

- [ ] **Step 5: 运行确认通过**

Run: `cd H:/claude项目/tiktok_downloader && python -m pytest tests/test_organizer.py -v`
Expected: 9 passed

- [ ] **Step 6: Commit**

```bash
cd "H:/claude项目" && git add tiktok_downloader && git commit -m "feat(downloader): 项目脚手架与剧名清洗、链接解析"
```

---

### Task 2: organizer.plan_downloads 分组编集

**Files:**
- Modify: `tiktok_downloader/organizer.py`
- Test: `tiktok_downloader/tests/test_organizer.py`

**Interfaces:**
- Consumes: `VideoItem`, `clean_series`
- Produces: `DownloadTask` dataclass：`video_id: str, series: str, filename: str`（如 `第01集.mp4`）
- Produces: `plan_downloads(items: list[VideoItem]) -> dict[str, list[DownloadTask]]`，key=剧名，list 按集号升序

- [ ] **Step 1: 写失败测试**（追加到 `tests/test_organizer.py`）

```python
from organizer import VideoItem, plan_downloads


def test_plan_downloads_groups_and_numbers_by_time():
    items = [
        VideoItem("b", 200, "Show A #fyp"),
        VideoItem("a", 100, "Show A"),
        VideoItem("c", 300, "Show B"),
    ]
    plan = plan_downloads(items)
    a = plan["Show A"]
    assert [t.video_id for t in a] == ["a", "b"]
    assert a[0].filename == "第01集.mp4"
    assert a[1].filename == "第02集.mp4"
    assert plan["Show B"][0].filename == "第01集.mp4"

def test_plan_downloads_three_digits_for_100_plus():
    items = [VideoItem(str(i), i, "Long") for i in range(100)]
    plan = plan_downloads(items)
    assert plan["Long"][0].filename == "第001集.mp4"
    assert plan["Long"][99].filename == "第100集.mp4"
```

- [ ] **Step 2: 运行确认失败**

Run: `cd H:/claude项目/tiktok_downloader && python -m pytest tests/test_organizer.py -v`
Expected: FAIL（`ImportError: plan_downloads`）

- [ ] **Step 3: 实现**（追加到 `organizer.py`）

```python
@dataclass
class DownloadTask:
    video_id: str
    series: str
    filename: str


def plan_downloads(items: list[VideoItem]) -> dict[str, list[DownloadTask]]:
    groups: dict[str, list[VideoItem]] = {}
    for it in items:
        groups.setdefault(clean_series(it.desc), []).append(it)
    plan: dict[str, list[DownloadTask]] = {}
    for series, eps in groups.items():
        eps.sort(key=lambda v: v.create_time)
        width = 3 if len(eps) >= 100 else 2
        plan[series] = [
            DownloadTask(v.id, series, f"第{i:0{width}d}集.mp4")
            for i, v in enumerate(eps, 1)
        ]
    return plan
```

- [ ] **Step 4: 运行确认通过**

Run: `cd H:/claude项目/tiktok_downloader && python -m pytest tests/test_organizer.py -v`
Expected: 11 passed

- [ ] **Step 5: Commit**

```bash
cd "H:/claude项目" && git add tiktok_downloader && git commit -m "feat(downloader): 按剧分组与时间序编集号"
```

---

### Task 3: cookies 导出（Playwright cookies → Netscape 文件）

**Files:**
- Create: `tiktok_downloader/cookies_io.py`
- Test: `tiktok_downloader/tests/test_cookies_io.py`

**Interfaces:**
- Produces: `write_netscape(cookies: list[dict], path: str) -> None`，`cookies` 为 Playwright `context.cookies()` 返回格式（键：`domain,path,secure,expires,name,value`）

- [ ] **Step 1: 写失败测试**

`tiktok_downloader/tests/test_cookies_io.py`:
```python
from cookies_io import write_netscape


def test_write_netscape(tmp_path):
    p = tmp_path / "c.txt"
    write_netscape([
        {"domain": ".tiktok.com", "path": "/", "secure": True,
         "expires": 1999999999, "name": "sid", "value": "abc"},
        {"domain": "www.tiktok.com", "path": "/", "secure": False,
         "expires": -1, "name": "s2", "value": "x"},
    ], str(p))
    lines = p.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "# Netscape HTTP Cookie File"
    assert ".tiktok.com\tTRUE\t/\tTRUE\t1999999999\tsid\tabc" in lines
    # 会话 cookie expires=-1 写 0；域不带点 domain_flag=FALSE
    assert "www.tiktok.com\tFALSE\t/\tFALSE\t0\ts2\tx" in lines
```

- [ ] **Step 2: 运行确认失败**

Run: `cd H:/claude项目/tiktok_downloader && python -m pytest tests/test_cookies_io.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现**

`tiktok_downloader/cookies_io.py`:
```python
def write_netscape(cookies: list[dict], path: str) -> None:
    lines = ["# Netscape HTTP Cookie File"]
    for c in cookies:
        domain = c["domain"]
        flag = "TRUE" if domain.startswith(".") else "FALSE"
        secure = "TRUE" if c.get("secure") else "FALSE"
        expires = int(c.get("expires") or 0)
        if expires < 0:
            expires = 0
        lines.append("\t".join([
            domain, flag, c.get("path", "/"), secure,
            str(expires), c["name"], c["value"],
        ]))
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
```

- [ ] **Step 4: 运行确认通过**

Run: `cd H:/claude项目/tiktok_downloader && python -m pytest tests/test_cookies_io.py -v`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
cd "H:/claude项目" && git add tiktok_downloader && git commit -m "feat(downloader): Netscape cookies 导出"
```

---

### Task 4: downloader 多线程下载引擎

**Files:**
- Create: `tiktok_downloader/downloader.py`
- Test: `tiktok_downloader/tests/test_downloader.py`

**Interfaces:**
- Consumes: `DownloadTask`（Task 2）
- Produces: `run_downloads(plan: dict[str, list[DownloadTask]], selected: set[str], base_dir: str, cookies_file: str, on_progress, stop_event, runner=None, max_workers=3) -> tuple[int, int]` 返回 `(成功数, 失败数)`
  - `on_progress(done: int, total: int, failed: int, msg: str)`：每完成一集调用
  - `runner(video_id: str, out_path: str, cookies_file: str) -> bool`：可注入以便测试；默认 `_run_ytdlp`
  - 已存在文件计入成功但不调 runner；失败任务在第一轮结束后串行重试一轮

- [ ] **Step 1: 写失败测试**

`tiktok_downloader/tests/test_downloader.py`:
```python
import threading
from organizer import DownloadTask
from downloader import run_downloads


def make_plan():
    return {"S": [DownloadTask("v1", "S", "第01集.mp4"),
                  DownloadTask("v2", "S", "第02集.mp4")],
            "T": [DownloadTask("v3", "T", "第01集.mp4")]}


def test_downloads_only_selected_and_reports(tmp_path):
    calls, msgs = [], []
    ok, fail = run_downloads(
        make_plan(), {"S"}, str(tmp_path), "c.txt",
        on_progress=lambda d, t, f, m: msgs.append((d, t, f)),
        stop_event=threading.Event(),
        runner=lambda vid, out, ck: calls.append(vid) or True,
        max_workers=1)
    assert sorted(calls) == ["v1", "v2"] and (ok, fail) == (2, 0)
    assert msgs[-1] == (2, 2, 0)


def test_skips_existing_files(tmp_path):
    (tmp_path / "S").mkdir()
    (tmp_path / "S" / "第01集.mp4").write_bytes(b"x")
    calls = []
    ok, fail = run_downloads(
        make_plan(), {"S"}, str(tmp_path), "c.txt",
        on_progress=lambda *a: None, stop_event=threading.Event(),
        runner=lambda vid, out, ck: calls.append(vid) or True, max_workers=1)
    assert calls == ["v2"] and ok == 2


def test_failed_retried_once(tmp_path):
    attempts = {"v1": 0}
    def flaky(vid, out, ck):
        attempts[vid] += 1
        return attempts[vid] >= 2   # 第一次失败，重试成功
    ok, fail = run_downloads(
        {"S": [DownloadTask("v1", "S", "第01集.mp4")]}, {"S"},
        str(tmp_path), "c.txt", on_progress=lambda *a: None,
        stop_event=threading.Event(), runner=flaky, max_workers=1)
    assert attempts["v1"] == 2 and (ok, fail) == (1, 0)


def test_stop_event_halts(tmp_path):
    ev = threading.Event(); ev.set()
    calls = []
    ok, fail = run_downloads(
        make_plan(), {"S", "T"}, str(tmp_path), "c.txt",
        on_progress=lambda *a: None, stop_event=ev,
        runner=lambda vid, out, ck: calls.append(vid) or True, max_workers=1)
    assert calls == []
```

- [ ] **Step 2: 运行确认失败**

Run: `cd H:/claude项目/tiktok_downloader && python -m pytest tests/test_downloader.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现**

`tiktok_downloader/downloader.py`:
```python
import os
import shutil
import subprocess
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor

from organizer import DownloadTask


def _run_ytdlp(video_id: str, out_path: str, cookies_file: str) -> bool:
    url = f"https://www.tiktok.com/@_/video/{video_id}"
    # 每次调用复制独立 cookies，避免 yt-dlp 并发回写同一文件的竞态
    fd, ck = tempfile.mkstemp(suffix=".txt")
    os.close(fd)
    try:
        shutil.copyfile(cookies_file, ck)
        r = subprocess.run(
            ["yt-dlp", "--cookies", ck, "-q", "--no-progress",
             "--retries", "5",
             "-o", out_path.replace(".mp4", ".%(ext)s"), url],
            capture_output=True, text=True, timeout=300)
        return r.returncode == 0
    except Exception:
        return False
    finally:
        try:
            os.remove(ck)
        except OSError:
            pass


def run_downloads(plan, selected, base_dir, cookies_file, on_progress,
                  stop_event, runner=None, max_workers=3):
    runner = runner or _run_ytdlp
    tasks: list[tuple[DownloadTask, str]] = []
    for series in plan:
        if series not in selected:
            continue
        folder = os.path.join(base_dir, series)
        for t in plan[series]:
            tasks.append((t, os.path.join(folder, t.filename)))

    total = len(tasks)
    done = 0
    failed: list[tuple[DownloadTask, str]] = []
    lock = threading.Lock()

    def work(item):
        nonlocal done
        t, out = item
        if stop_event.is_set():
            return
        os.makedirs(os.path.dirname(out), exist_ok=True)
        ok = True if os.path.exists(out) else runner(t.video_id, out, cookies_file)
        with lock:
            done += 1
            if not ok:
                failed.append(item)
            on_progress(done, total, len(failed),
                        f"{'OK' if ok else 'FAIL'} {t.series}/{t.filename}")

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        list(ex.map(work, tasks))

    # 失败串行重试一轮
    still_failed = 0
    for t, out in failed:
        if stop_event.is_set():
            still_failed += 1
            continue
        if os.path.exists(out) or runner(t.video_id, out, cookies_file):
            continue
        still_failed += 1
        on_progress(done, total, still_failed, f"重试仍失败 {t.series}/{t.filename}")

    if stop_event.is_set():
        return done - len(failed), still_failed
    return total - still_failed, still_failed
```

- [ ] **Step 4: 运行确认通过**

Run: `cd H:/claude项目/tiktok_downloader && python -m pytest tests/test_downloader.py -v`
Expected: 4 passed（stop 测试中 done=0，进度回调不触发，返回 (0,0)）

- [ ] **Step 5: 全量测试并 Commit**

Run: `cd H:/claude项目/tiktok_downloader && python -m pytest -v` → Expected: 16 passed

```bash
cd "H:/claude项目" && git add tiktok_downloader && git commit -m "feat(downloader): 多线程下载引擎（跳过已存在/失败重试/可停止）"
```

---

### Task 5: collector 采集模块（Playwright + 专用 Chrome）

**Files:**
- Create: `tiktok_downloader/collector.py`
- Create: `tiktok_downloader/config.py`

**Interfaces:**
- Consumes: `VideoItem`（Task 2）、`write_netscape`（Task 3）、`parse_input`（Task 1）
- Produces: `collect(url: str, kind: str, profile_dir: str, cookies_out: str, on_status, chrome_path: str | None = None) -> list[VideoItem]`
  - `on_status(msg: str)`：进度文案回调
  - 抛 `NeedLoginError`（登录墙）、`ChromeNotFoundError`（无 Chrome）
- Produces: `config.load() -> dict` / `config.save(cfg: dict)`（存 `chrome_path`、`last_dir`，JSON 于程序目录 `config.json`）

无法自动化测试（需真实浏览器），以 Task 7 手动验收。

- [ ] **Step 1: 安装 playwright**

```bash
pip install playwright
```
（不需要 `playwright install`，用本机 Chrome channel）

- [ ] **Step 2: 实现 config.py**

```python
import json
import os

_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


def load() -> dict:
    try:
        with open(_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save(cfg: dict) -> None:
    with open(_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
```

- [ ] **Step 3: 实现 collector.py**

```python
import json
import re
import subprocess
import time

from cookies_io import write_netscape
from organizer import VideoItem


class NeedLoginError(Exception):
    pass


class ChromeNotFoundError(Exception):
    pass


def _collect_single(url: str) -> list[VideoItem]:
    r = subprocess.run(
        ["yt-dlp", "--no-download", "--print", "%(id)s\t%(timestamp)s\t%(title)s", url],
        capture_output=True, text=True, timeout=120, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"获取视频信息失败: {r.stderr[-200:]}")
    vid, ts, title = r.stdout.strip().split("\t", 2)
    ts = int(ts) if ts.isdigit() else 0
    return [VideoItem(vid, ts, title)]


def collect(url, kind, profile_dir, cookies_out, on_status, chrome_path=None):
    if kind == "video":
        on_status("获取单视频信息…")
        return _collect_single(url)

    from playwright.sync_api import sync_playwright

    seen: dict[str, VideoItem] = {}
    state = {"has_more": True, "batches": 0}

    with sync_playwright() as p:
        kwargs = dict(user_data_dir=profile_dir, headless=False,
                      args=["--lang=en-US"])
        if chrome_path:
            kwargs["executable_path"] = chrome_path
        else:
            kwargs["channel"] = "chrome"
        try:
            ctx = p.chromium.launch_persistent_context(**kwargs)
        except Exception as e:
            raise ChromeNotFoundError(str(e)) from e

        page = ctx.new_page()

        def on_response(res):
            if "api/post/item_list" not in res.url:
                return
            try:
                data = res.json()
            except Exception:
                return
            for it in data.get("itemList") or []:
                seen[it["id"]] = VideoItem(
                    it["id"], int(it.get("createTime") or 0),
                    re.sub(r"[\t\n]", " ", it.get("desc") or ""))
            state["has_more"] = bool(data.get("hasMore"))
            state["batches"] += 1
            on_status(f"已采集 {len(seen)} 个视频…")

        page.on("response", on_response)
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(6000)

        stall, last = 0, 0
        for i in range(500):
            if not state["has_more"] and state["batches"] > 0:
                break
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(1500)
            if len(seen) == last:
                stall += 1
                if stall >= 20:
                    break
            else:
                stall, last = 0, len(seen)
            # 30 秒仍无数据且出现登录墙 → 要求登录
            if i == 20 and not seen:
                if page.locator("#loginContainer, [data-e2e='login-modal']").count():
                    ctx.close()
                    raise NeedLoginError("需要登录")

        # DOM 兜底补充
        for a in page.eval_on_selector_all(
                "a[href*='/video/']", "els => els.map(a => a.href)"):
            m = re.search(r"video/(\d+)", a)
            if m and m.group(1) not in seen:
                seen[m.group(1)] = VideoItem(m.group(1), 0, "")

        write_netscape(ctx.cookies(), cookies_out)
        ctx.close()

    if not seen:
        raise NeedLoginError("未采集到任何视频，可能需要登录")
    on_status(f"采集完成，共 {len(seen)} 个视频")
    return list(seen.values())
```

- [ ] **Step 4: 冒烟验证（语法+导入）**

Run: `cd H:/claude项目/tiktok_downloader && python -c "import collector, config; print('ok')"`
Expected: `ok`

- [ ] **Step 5: Commit**

```bash
cd "H:/claude项目" && git add tiktok_downloader && git commit -m "feat(downloader): Playwright 采集模块与配置存取"
```

---

### Task 6: app.py tkinter 界面

**Files:**
- Create: `tiktok_downloader/app.py`

**Interfaces:**
- Consumes: `parse_input, plan_downloads, VideoItem`（organizer）、`collect, NeedLoginError, ChromeNotFoundError`（collector）、`run_downloads`（downloader）、`config`
- Produces: `python app.py` 启动的 GUI 主程序

- [ ] **Step 1: 实现 app.py**

```python
import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import config
from collector import ChromeNotFoundError, NeedLoginError, collect
from downloader import run_downloads
from organizer import parse_input, plan_downloads

BASE = os.path.dirname(os.path.abspath(__file__))
PROFILE_DIR = os.path.join(BASE, "chrome_profile")
COOKIES = os.path.join(BASE, "cookies.txt")


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("TikTok 剧集下载器")
        root.geometry("640x560")
        self.q = queue.Queue()
        self.plan = {}
        self.stop_event = threading.Event()
        cfg = config.load()

        top = ttk.Frame(root, padding=8); top.pack(fill="x")
        ttk.Label(top, text="账号/视频链接:").grid(row=0, column=0, sticky="w")
        self.url_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.url_var, width=52).grid(row=0, column=1, padx=4)
        self.btn_collect = ttk.Button(top, text="采集", command=self.on_collect)
        self.btn_collect.grid(row=0, column=2)

        ttk.Label(top, text="下载目录:").grid(row=1, column=0, sticky="w", pady=4)
        self.dir_var = tk.StringVar(value=cfg.get("last_dir", os.path.join(BASE, "下载")))
        ttk.Entry(top, textvariable=self.dir_var, width=52).grid(row=1, column=1, padx=4)
        ttk.Button(top, text="浏览...", command=self.on_browse).grid(row=1, column=2)

        mid = ttk.Frame(root, padding=(8, 0)); mid.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(mid, columns=("eps",), selectmode="none", height=12)
        self.tree.heading("#0", text="剧名（点击勾选/取消）")
        self.tree.heading("eps", text="集数")
        self.tree.column("eps", width=60, anchor="center")
        self.tree.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(mid, command=self.tree.yview); sb.pack(side="right", fill="y")
        self.tree.config(yscrollcommand=sb.set)
        self.tree.bind("<Button-1>", self.on_tree_click)
        self.checked: dict[str, bool] = {}

        btns = ttk.Frame(root, padding=8); btns.pack(fill="x")
        ttk.Button(btns, text="全选", command=lambda: self.set_all(True)).pack(side="left")
        ttk.Button(btns, text="全不选", command=lambda: self.set_all(False)).pack(side="left", padx=4)
        self.btn_dl = ttk.Button(btns, text="开始下载", command=self.on_download, state="disabled")
        self.btn_dl.pack(side="left", padx=12)
        self.btn_stop = ttk.Button(btns, text="停止", command=self.on_stop, state="disabled")
        self.btn_stop.pack(side="left")

        self.prog = ttk.Progressbar(root, maximum=100); self.prog.pack(fill="x", padx=8)
        self.status = tk.StringVar(value="就绪")
        ttk.Label(root, textvariable=self.status).pack(anchor="w", padx=8)
        self.log = tk.Text(root, height=8, state="disabled")
        self.log.pack(fill="both", expand=False, padx=8, pady=(4, 8))
        root.after(100, self.poll)

    # ---------- 界面事件 ----------
    def on_browse(self):
        d = filedialog.askdirectory()
        if d:
            self.dir_var.set(d)

    def on_tree_click(self, ev):
        iid = self.tree.identify_row(ev.y)
        if iid:
            self.checked[iid] = not self.checked.get(iid, True)
            self.render_row(iid)

    def set_all(self, val: bool):
        for iid in self.checked:
            self.checked[iid] = val
            self.render_row(iid)

    def render_row(self, series: str):
        mark = "☑" if self.checked[series] else "☐"
        self.tree.item(series, text=f"{mark} {series}")

    def logline(self, msg: str):
        self.log.config(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.log.config(state="disabled")

    # ---------- 采集 ----------
    def on_collect(self):
        try:
            kind, url = parse_input(self.url_var.get())
        except ValueError as e:
            messagebox.showerror("链接错误", str(e))
            return
        self.btn_collect.config(state="disabled")
        self.status.set("采集中…（首次使用请在打开的浏览器里登录 TikTok）")
        threading.Thread(target=self.collect_worker, args=(url, kind), daemon=True).start()

    def collect_worker(self, url: str, kind: str):
        cfg = config.load()
        try:
            items = collect(url, kind, PROFILE_DIR, COOKIES,
                            on_status=lambda m: self.q.put(("status", m)),
                            chrome_path=cfg.get("chrome_path"))
            self.q.put(("collected", items))
        except NeedLoginError:
            self.q.put(("need_login", url, kind))
        except ChromeNotFoundError as e:
            self.q.put(("no_chrome", str(e)))
        except Exception as e:
            self.q.put(("error", f"采集失败: {e}"))

    # ---------- 下载 ----------
    def on_download(self):
        selected = {s for s, v in self.checked.items() if v}
        if not selected:
            messagebox.showinfo("提示", "请先勾选要下载的剧")
            return
        base = self.dir_var.get().strip()
        os.makedirs(base, exist_ok=True)
        cfg = config.load(); cfg["last_dir"] = base; config.save(cfg)
        self.stop_event.clear()
        self.btn_dl.config(state="disabled"); self.btn_stop.config(state="normal")
        threading.Thread(target=self.download_worker,
                         args=(selected, base), daemon=True).start()

    def download_worker(self, selected: set, base: str):
        try:
            ok, fail = run_downloads(
                self.plan, selected, base, COOKIES,
                on_progress=lambda d, t, f, m: self.q.put(("prog", d, t, f, m)),
                stop_event=self.stop_event)
            self.q.put(("done", ok, fail))
        except Exception as e:
            self.q.put(("error", f"下载失败: {e}"))

    def on_stop(self):
        self.stop_event.set()
        self.status.set("正在停止…（等待在途任务完成）")

    # ---------- 队列轮询 ----------
    def poll(self):
        try:
            while True:
                msg = self.q.get_nowait()
                self.handle(msg)
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    def handle(self, msg):
        kind = msg[0]
        if kind == "status":
            self.status.set(msg[1])
        elif kind == "collected":
            self.plan = plan_downloads(msg[1])
            self.tree.delete(*self.tree.get_children())
            self.checked.clear()
            for series in sorted(self.plan, key=lambda s: -len(self.plan[s])):
                self.tree.insert("", "end", iid=series, values=(len(self.plan[series]),))
                self.checked[series] = True
                self.render_row(series)
            total = sum(len(v) for v in self.plan.values())
            self.status.set(f"采集完成：{len(self.plan)} 部剧 / {total} 集")
            self.btn_collect.config(state="normal")
            self.btn_dl.config(state="normal")
        elif kind == "prog":
            _, d, t, f, m = msg
            self.prog.config(maximum=max(t, 1), value=d)
            self.status.set(f"下载中 {d}/{t}  失败:{f}")
            self.logline(m)
        elif kind == "done":
            _, ok, fail = msg
            self.status.set(f"完成：成功 {ok}，失败 {fail}")
            self.btn_dl.config(state="normal"); self.btn_stop.config(state="disabled")
            messagebox.showinfo("完成", f"下载结束\n成功 {ok} 集，失败 {fail} 集")
        elif kind == "need_login":
            self.btn_collect.config(state="normal")
            self.status.set("需要登录")
            if messagebox.askretrycancel(
                    "需要登录", "请在弹出的浏览器里登录 TikTok，然后点[重试]"):
                self.url_var.set(self.url_var.get())
                self.on_collect()
        elif kind == "no_chrome":
            self.btn_collect.config(state="normal")
            self.status.set("未找到 Chrome")
            if messagebox.askokcancel("未找到 Chrome", "请选择 chrome.exe 的位置"):
                p = filedialog.askopenfilename(
                    title="选择 chrome.exe", filetypes=[("Chrome", "chrome.exe")])
                if p:
                    cfg = config.load(); cfg["chrome_path"] = p; config.save(cfg)
                    self.on_collect()
        elif kind == "error":
            self.btn_collect.config(state="normal")
            self.btn_dl.config(state="normal" if self.plan else "disabled")
            self.btn_stop.config(state="disabled")
            self.status.set(msg[1])
            messagebox.showerror("错误", msg[1])


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
```

- [ ] **Step 2: 冒烟验证（导入不报错）**

Run: `cd H:/claude项目/tiktok_downloader && python -c "import ast; ast.parse(open('app.py', encoding='utf-8').read()); print('ok')"`
Expected: `ok`

- [ ] **Step 3: 全量单测回归**

Run: `cd H:/claude项目/tiktok_downloader && python -m pytest -v`
Expected: 16 passed

- [ ] **Step 4: Commit**

```bash
cd "H:/claude项目" && git add tiktok_downloader && git commit -m "feat(downloader): tkinter 主界面"
```

---

### Task 7: 手动验收（真实账号小规模）

**Files:** 无新文件

- [ ] **Step 1: 启动程序**

Run: `cd H:/claude项目/tiktok_downloader && python app.py`
Expected: 窗口出现，控件齐全

- [ ] **Step 2: 采集验收**

输入 `https://www.tiktok.com/@aidramalabs_anime2` → 点采集：
- 专用 Chrome 弹出（首次需登录 TikTok，登录后点重试）
- 状态栏计数持续上涨，最终 ≈ 1579 个 / 150+ 部剧（**> 6 即证明登录态与拦截生效**）
- 剧集列表出现且默认全选

- [ ] **Step 3: 下载验收**

全不选 → 只勾选一部 5 集左右的短剧（如 The Erased 7）→ 选一个空目录 → 开始下载：
- 目录出现 `剧名/第01集.mp4 …`，进度条走满，弹"完成"
- 再次点开始下载 → 秒完成（跳过已存在）

- [ ] **Step 4: 单视频验收**

粘一个单视频链接 → 采集 → 列表出现 1 项 → 下载成功

- [ ] **Step 5: Commit 收尾**

```bash
cd "H:/claude项目" && git add -A tiktok_downloader && git commit -m "chore(downloader): 手动验收通过"
```
（`chrome_profile/`、`config.json`、`cookies.txt`、`下载/` 加入 `.gitignore`：）

```
tiktok_downloader/chrome_profile/
tiktok_downloader/config.json
tiktok_downloader/cookies.txt
tiktok_downloader/下载/
```

---

## Self-Review 结果

- **Spec 覆盖**：界面布局(T6)、采集/登录墙/hasMore(T5)、分组编集规则(T1/T2)、cookies 独立副本(T4 `_run_ytdlp`)、断点跳过/失败重试/停止(T4)、Chrome 路径配置(T5/T6)、单视频输入(T1 parse_input + T5 _collect_single)、测试策略(T1-T4 单测 + T7 手动) — 全覆盖
- **占位符**：无
- **类型一致性**：`VideoItem(id, create_time, desc)`、`DownloadTask(video_id, series, filename)`、`run_downloads(plan, selected, base_dir, cookies_file, on_progress, stop_event, runner, max_workers)` 在 T2/T4/T6 中签名一致；`collect(url, kind, profile_dir, cookies_out, on_status, chrome_path)` 在 T5/T6 一致
