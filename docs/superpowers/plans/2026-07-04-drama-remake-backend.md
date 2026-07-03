# AI 短剧扒剧与仿写程序 — 后端实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现完整后端：Gemini 视频扒剧 + 五阶段仿写流水线 + HTTP API（含 SSE 进度），可用 pytest 和 curl 验证。

**Architecture:** FastAPI 单进程应用。内容产物全部为文件系统纯文本；SQLite 只存每集扒剧状态（断点续跑）。视频理解仅走 Gemini Files API；文本环节走统一的 OpenAI 兼容 chat/completions 客户端（DeepSeek/GPT/Kimi/Gemini-compat 均适用）。阶段②~⑤为单次/少次 LLM 调用，状态不落库（重启后用户重新点击即可）；阶段①为长任务，逐集状态持久化。

**Tech Stack:** Python 3.11+、FastAPI、uvicorn、pydantic v2、PyYAML、httpx、google-genai、sqlite3（标准库）、pytest + pytest-asyncio

**规格文档:** `docs/superpowers/specs/2026-07-04-drama-remake-design.md`

## Global Constraints

- Python ≥ 3.11；所有源码在 `backend/` 下，包名 `app`
- 剧本场次头格式：`集-场号  时间  内/外  地点`，动作行以 `▲` 开头，台词 `角色(语气)：台词`，标注 `【字幕：…】【特效：…】`
- 项目数据目录结构（相对 `data_dir`）：`projects/<pid>/project.json`、`episodes/ep{NNN}.script.md`、`episodes/ep{NNN}.meta.json`、`analysis/report.md`、`settings/new_drama.md`、`outline/outline.md`、`scripts/ep{NNN}.md`（NNN 为 3 位零填充集数）
- 每集扒剧状态枚举：`pending / uploading / analyzing / done / failed`
- 全局配置文件 `backend/config.yaml`（见 Task 1 的 example）
- 所有文件读写 `encoding="utf-8"`
- 测试命令统一在 `backend/` 目录下运行：`python -m pytest tests/ -v`
- 每个任务完成后 git commit（仓库根 `H:\claude项目`）

## File Structure

```
backend/
├── requirements.txt
├── config.yaml.example
├── pytest.ini
├── app/
│   ├── __init__.py
│   ├── config.py          # 配置加载（pydantic 校验）
│   ├── script_format.py   # 剧本解析与校验
│   ├── storage.py         # 项目/产物文件存储层
│   ├── db.py              # SQLite 集状态库
│   ├── llm.py             # TextLLM(OpenAI兼容) + GeminiVideo + 重试
│   ├── prompts.py         # 五阶段全部 prompt
│   ├── pipeline.py        # 阶段①~⑤业务函数
│   ├── engine.py          # 并发批处理 + EventBus(SSE)
│   ├── export.py          # 全剧汇总导出
│   ├── api.py             # 全部 HTTP 路由
│   └── main.py            # create_app 组装 + uvicorn 入口
└── tests/
    ├── conftest.py
    ├── test_config.py
    ├── test_script_format.py
    ├── test_storage.py
    ├── test_db.py
    ├── test_llm.py
    ├── test_pipeline.py
    ├── test_engine.py
    ├── test_export.py
    └── test_api.py
```

---

### Task 1: 项目脚手架与配置加载

**Files:**
- Create: `backend/requirements.txt`, `backend/pytest.ini`, `backend/config.yaml.example`, `backend/app/__init__.py`, `backend/app/config.py`, `backend/tests/test_config.py`, `.gitignore`

**Interfaces:**
- Produces: `load_config(path) -> AppConfig`；`AppConfig` 字段：`gemini: GeminiConfig(api_key, model)`、`text_llm: TextLLMConfig(provider, providers: dict[str, ProviderConfig(base_url, api_key, model)])`、`concurrency: int=3`、`retries: int=2`、`data_dir: str="data"`

- [ ] **Step 1: 创建脚手架文件**

`.gitignore`（仓库根）：

```
__pycache__/
*.pyc
.venv/
backend/config.yaml
backend/data/
.pytest_cache/
node_modules/
dist/
```

`backend/requirements.txt`：

```
fastapi
uvicorn[standard]
pydantic>=2
PyYAML
httpx
google-genai
pytest
pytest-asyncio
```

`backend/pytest.ini`：

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
```

`backend/config.yaml.example`：

```yaml
gemini:
  api_key: "YOUR_GEMINI_API_KEY"
  model: "gemini-2.5-pro"

text_llm:
  provider: "deepseek"          # 当前使用的文本模型，对应 providers 里的键
  providers:
    deepseek:
      base_url: "https://api.deepseek.com/v1"
      api_key: "YOUR_KEY"
      model: "deepseek-chat"
    gemini:
      base_url: "https://generativelanguage.googleapis.com/v1beta/openai"
      api_key: "YOUR_GEMINI_API_KEY"
      model: "gemini-2.5-pro"

concurrency: 3
retries: 2
data_dir: "data"
```

`backend/app/__init__.py`：空文件。

安装依赖：`cd backend && pip install -r requirements.txt`

- [ ] **Step 2: 写失败测试** `backend/tests/test_config.py`

```python
from pathlib import Path
from app.config import load_config

YAML = """
gemini: {api_key: "gk", model: "gemini-2.5-pro"}
text_llm:
  provider: "deepseek"
  providers:
    deepseek: {base_url: "https://api.deepseek.com/v1", api_key: "dk", model: "deepseek-chat"}
"""

def test_load_config(tmp_path: Path):
    p = tmp_path / "config.yaml"
    p.write_text(YAML, encoding="utf-8")
    cfg = load_config(p)
    assert cfg.gemini.api_key == "gk"
    assert cfg.text_llm.providers["deepseek"].model == "deepseek-chat"
    assert cfg.concurrency == 3      # 默认值
    assert cfg.retries == 2
    assert cfg.data_dir == "data"

def test_active_provider(tmp_path: Path):
    p = tmp_path / "config.yaml"
    p.write_text(YAML, encoding="utf-8")
    cfg = load_config(p)
    ap = cfg.text_llm.active()
    assert ap.base_url == "https://api.deepseek.com/v1"
```

- [ ] **Step 3: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_config.py -v`
Expected: FAIL（ModuleNotFoundError / ImportError）

- [ ] **Step 4: 实现** `backend/app/config.py`

```python
from pathlib import Path

import yaml
from pydantic import BaseModel


class ProviderConfig(BaseModel):
    base_url: str
    api_key: str
    model: str


class GeminiConfig(BaseModel):
    api_key: str
    model: str = "gemini-2.5-pro"


class TextLLMConfig(BaseModel):
    provider: str
    providers: dict[str, ProviderConfig]

    def active(self) -> ProviderConfig:
        return self.providers[self.provider]


class AppConfig(BaseModel):
    gemini: GeminiConfig
    text_llm: TextLLMConfig
    concurrency: int = 3
    retries: int = 2
    data_dir: str = "data"


def load_config(path: str | Path = "config.yaml") -> AppConfig:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return AppConfig.model_validate(data)
```

- [ ] **Step 5: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_config.py -v`
Expected: 2 passed

- [ ] **Step 6: Commit**

```bash
git add .gitignore backend/
git commit -m "feat: 后端脚手架与配置加载"
```

---

### Task 2: 剧本格式解析与校验

**Files:**
- Create: `backend/app/script_format.py`, `backend/tests/test_script_format.py`

**Interfaces:**
- Produces:
  - `parse_script(text: str) -> EpisodeScript`（dataclass：`episode: int`, `scenes: list[Scene]`；`Scene`：`episode:int, number:int, time:str, place_type:str, location:str, lines:list[str]`）
  - `validate_script(text: str, expected_episode: int) -> list[str]`（返回错误信息列表，空列表=合法）

- [ ] **Step 1: 写失败测试** `backend/tests/test_script_format.py`

```python
from app.script_format import parse_script, validate_script

SAMPLE = """1-1  夜  外  博物馆门前
出场人物：林修(仅声音)

▲ 地面水洼映出红灯笼的倒影。
【字幕：第九号私人博物馆】
林修(vo)：我叫林修。

1-2  夜  内  博物馆大殿
出场人物：林修

▲ 殿内陈列着青铜器。
林修(惊诧)：哎，你怎么烧了？
"""

def test_parse_scenes():
    s = parse_script(SAMPLE)
    assert s.episode == 1
    assert len(s.scenes) == 2
    assert s.scenes[0].number == 1
    assert s.scenes[0].time == "夜"
    assert s.scenes[0].place_type == "外"
    assert s.scenes[0].location == "博物馆门前"
    assert "林修(vo)：我叫林修。" in s.scenes[0].lines

def test_validate_ok():
    assert validate_script(SAMPLE, expected_episode=1) == []

def test_validate_wrong_episode():
    errs = validate_script(SAMPLE, expected_episode=2)
    assert any("集数" in e for e in errs)

def test_validate_scene_gap():
    bad = SAMPLE.replace("1-2", "1-3")
    errs = validate_script(bad, expected_episode=1)
    assert any("场号" in e for e in errs)

def test_validate_no_scene():
    errs = validate_script("随便一段文字，没有场次头", expected_episode=1)
    assert any("场次" in e for e in errs)
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_script_format.py -v`
Expected: FAIL（ImportError）

- [ ] **Step 3: 实现** `backend/app/script_format.py`

```python
import re
from dataclasses import dataclass, field

# 场次头：`1-4  夜  内  博物馆柜台`
SCENE_RE = re.compile(r"^(\d+)-(\d+)\s+(\S+)\s+(内外|内|外)\s+(\S.*)$")


@dataclass
class Scene:
    episode: int
    number: int
    time: str
    place_type: str
    location: str
    lines: list[str] = field(default_factory=list)


@dataclass
class EpisodeScript:
    episode: int
    scenes: list[Scene]


def parse_script(text: str) -> EpisodeScript:
    scenes: list[Scene] = []
    for raw in text.splitlines():
        line = raw.rstrip()
        m = SCENE_RE.match(line.strip())
        if m:
            scenes.append(Scene(
                episode=int(m.group(1)), number=int(m.group(2)),
                time=m.group(3), place_type=m.group(4),
                location=m.group(5).strip(),
            ))
        elif scenes and line.strip():
            scenes[-1].lines.append(line.strip())
    episode = scenes[0].episode if scenes else 0
    return EpisodeScript(episode=episode, scenes=scenes)


def validate_script(text: str, expected_episode: int) -> list[str]:
    errors: list[str] = []
    script = parse_script(text)
    if not script.scenes:
        errors.append("未找到任何场次头")
        return errors
    for sc in script.scenes:
        if sc.episode != expected_episode:
            errors.append(f"场 {sc.episode}-{sc.number} 集数与期望({expected_episode})不符")
    numbers = [sc.number for sc in script.scenes]
    for i, n in enumerate(numbers, start=1):
        if n != i:
            errors.append(f"场号不连续：第 {i} 个场次的场号是 {n}")
            break
    return errors
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_script_format.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/script_format.py backend/tests/test_script_format.py
git commit -m "feat: 剧本格式解析与校验"
```

---

### Task 3: 项目存储层

**Files:**
- Create: `backend/app/storage.py`, `backend/tests/test_storage.py`

**Interfaces:**
- Produces:
  - `scan_videos(video_dir: Path) -> list[Path]`（按文件名自然排序，仅视频扩展名）
  - `class ProjectStore(data_dir: Path)`：
    - `create_project(name: str, video_dir: str) -> dict`（返回 project dict，含 `id/name/video_dir/episodes`；`episodes` 为 `[{"episode": 1, "file": "第01集.mp4"}, ...]`，创建时自动扫描）
    - `list_projects() -> list[dict]` / `get_project(pid: str) -> dict` / `save_project(project: dict) -> None`
    - `project_dir(pid) -> Path`
    - `episode_script_path(pid, ep: int) -> Path`、`episode_meta_path(pid, ep) -> Path`、`new_script_path(pid, ep) -> Path`
    - `artifact_path(pid, kind: str) -> Path`（kind ∈ `analysis|settings|outline`，对应 `analysis/report.md`、`settings/new_drama.md`、`outline/outline.md`）
    - `read(path) -> str | None`（不存在返回 None）、`write(path, text) -> None`（自动建父目录）

- [ ] **Step 1: 写失败测试** `backend/tests/test_storage.py`

```python
from pathlib import Path
from app.storage import ProjectStore, scan_videos

def make_videos(d: Path, names: list[str]):
    d.mkdir(parents=True, exist_ok=True)
    for n in names:
        (d / n).write_bytes(b"\x00")

def test_scan_natural_order(tmp_path: Path):
    vd = tmp_path / "videos"
    make_videos(vd, ["第10集.mp4", "第2集.mp4", "第1集.mp4", "notes.txt"])
    files = scan_videos(vd)
    assert [f.name for f in files] == ["第1集.mp4", "第2集.mp4", "第10集.mp4"]

def test_create_and_get_project(tmp_path: Path):
    vd = tmp_path / "videos"
    make_videos(vd, ["ep1.mp4", "ep2.mp4"])
    store = ProjectStore(tmp_path / "data")
    p = store.create_project("测试剧", str(vd))
    assert p["name"] == "测试剧"
    assert p["episodes"] == [
        {"episode": 1, "file": "ep1.mp4"},
        {"episode": 2, "file": "ep2.mp4"},
    ]
    assert store.get_project(p["id"])["name"] == "测试剧"
    assert [x["id"] for x in store.list_projects()] == [p["id"]]

def test_paths_and_io(tmp_path: Path):
    store = ProjectStore(tmp_path / "data")
    vd = tmp_path / "v"; make_videos(vd, ["a.mp4"])
    p = store.create_project("x", str(vd))
    sp = store.episode_script_path(p["id"], 3)
    assert sp.name == "ep003.script.md"
    assert store.read(sp) is None
    store.write(sp, "内容")
    assert store.read(sp) == "内容"
    assert store.artifact_path(p["id"], "analysis").name == "report.md"
    assert store.new_script_path(p["id"], 12).name == "ep012.md"
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_storage.py -v`
Expected: FAIL（ImportError）

- [ ] **Step 3: 实现** `backend/app/storage.py`

```python
import json
import re
import uuid
from pathlib import Path

VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".avi", ".ts", ".webm", ".flv"}

_ARTIFACTS = {
    "analysis": ("analysis", "report.md"),
    "settings": ("settings", "new_drama.md"),
    "outline": ("outline", "outline.md"),
}


def _natural_key(name: str):
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", name)]


def scan_videos(video_dir: Path) -> list[Path]:
    files = [f for f in video_dir.iterdir()
             if f.is_file() and f.suffix.lower() in VIDEO_EXTS]
    return sorted(files, key=lambda f: _natural_key(f.name))


class ProjectStore:
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        (self.data_dir / "projects").mkdir(parents=True, exist_ok=True)

    def project_dir(self, pid: str) -> Path:
        return self.data_dir / "projects" / pid

    def _project_json(self, pid: str) -> Path:
        return self.project_dir(pid) / "project.json"

    def create_project(self, name: str, video_dir: str) -> dict:
        pid = uuid.uuid4().hex[:8]
        files = scan_videos(Path(video_dir))
        project = {
            "id": pid,
            "name": name,
            "video_dir": video_dir,
            "episodes": [{"episode": i + 1, "file": f.name}
                         for i, f in enumerate(files)],
        }
        self.save_project(project)
        return project

    def save_project(self, project: dict) -> None:
        self.write(self._project_json(project["id"]),
                   json.dumps(project, ensure_ascii=False, indent=2))

    def get_project(self, pid: str) -> dict:
        return json.loads(self._project_json(pid).read_text(encoding="utf-8"))

    def list_projects(self) -> list[dict]:
        out = []
        for d in sorted((self.data_dir / "projects").iterdir()):
            pj = d / "project.json"
            if pj.exists():
                out.append(json.loads(pj.read_text(encoding="utf-8")))
        return out

    def episode_script_path(self, pid: str, ep: int) -> Path:
        return self.project_dir(pid) / "episodes" / f"ep{ep:03d}.script.md"

    def episode_meta_path(self, pid: str, ep: int) -> Path:
        return self.project_dir(pid) / "episodes" / f"ep{ep:03d}.meta.json"

    def new_script_path(self, pid: str, ep: int) -> Path:
        return self.project_dir(pid) / "scripts" / f"ep{ep:03d}.md"

    def artifact_path(self, pid: str, kind: str) -> Path:
        sub, fname = _ARTIFACTS[kind]
        return self.project_dir(pid) / sub / fname

    def read(self, path: Path) -> str | None:
        return path.read_text(encoding="utf-8") if path.exists() else None

    def write(self, path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_storage.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/storage.py backend/tests/test_storage.py
git commit -m "feat: 项目存储层"
```

---

### Task 4: SQLite 集状态库

**Files:**
- Create: `backend/app/db.py`, `backend/tests/test_db.py`

**Interfaces:**
- Produces: `class StatusDB(path: Path)`：
  - `set_status(pid: str, ep: int, status: str, error: str = "") -> None`（UPSERT）
  - `get_statuses(pid: str) -> dict[int, dict]`（`{ep: {"status": str, "error": str}}`）
  - `close() -> None`
  - 状态枚举：`pending / uploading / analyzing / done / failed`

- [ ] **Step 1: 写失败测试** `backend/tests/test_db.py`

```python
from pathlib import Path
from app.db import StatusDB

def test_set_and_get(tmp_path: Path):
    db = StatusDB(tmp_path / "status.db")
    db.set_status("p1", 1, "pending")
    db.set_status("p1", 1, "analyzing")
    db.set_status("p1", 2, "failed", error="timeout")
    s = db.get_statuses("p1")
    assert s[1]["status"] == "analyzing"
    assert s[2] == {"status": "failed", "error": "timeout"}
    assert db.get_statuses("p2") == {}
    db.close()

def test_persistence(tmp_path: Path):
    p = tmp_path / "status.db"
    db = StatusDB(p)
    db.set_status("p1", 1, "done")
    db.close()
    db2 = StatusDB(p)
    assert db2.get_statuses("p1")[1]["status"] == "done"
    db2.close()
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_db.py -v`
Expected: FAIL（ImportError）

- [ ] **Step 3: 实现** `backend/app/db.py`

```python
import sqlite3
import threading
from pathlib import Path


class StatusDB:
    """每集扒剧状态，用于断点续跑。单文件 SQLite，线程安全。"""

    def __init__(self, path: Path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock:
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS episode_status ("
                " project_id TEXT NOT NULL,"
                " episode INTEGER NOT NULL,"
                " status TEXT NOT NULL,"
                " error TEXT NOT NULL DEFAULT '',"
                " PRIMARY KEY (project_id, episode))"
            )
            self._conn.commit()

    def set_status(self, pid: str, ep: int, status: str, error: str = "") -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO episode_status (project_id, episode, status, error)"
                " VALUES (?, ?, ?, ?)"
                " ON CONFLICT(project_id, episode)"
                " DO UPDATE SET status=excluded.status, error=excluded.error",
                (pid, ep, status, error),
            )
            self._conn.commit()

    def get_statuses(self, pid: str) -> dict[int, dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT episode, status, error FROM episode_status"
                " WHERE project_id=?", (pid,),
            ).fetchall()
        return {ep: {"status": st, "error": err} for ep, st, err in rows}

    def close(self) -> None:
        self._conn.close()
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_db.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/db.py backend/tests/test_db.py
git commit -m "feat: SQLite 集状态库"
```

---

### Task 5: LLM 适配层（TextLLM + GeminiVideo + 重试）

**Files:**
- Create: `backend/app/llm.py`, `backend/tests/test_llm.py`

**Interfaces:**
- Consumes: `AppConfig`（Task 1）
- Produces:
  - `async with_retry(fn: Callable[[], Awaitable[T]], attempts: int, base_delay: float = 2.0) -> T`（指数退避：2s、4s、8s…）
  - `class TextLLM(base_url, api_key, model)`：`async generate(system: str, user: str, temperature: float = 0.7) -> str`
  - `make_text_llm(cfg: AppConfig) -> TextLLM`（按 `cfg.text_llm.provider` 选择）
  - `class GeminiVideo(api_key, model)`：`async analyze(video_path: Path, prompt: str) -> str`（上传→轮询 ACTIVE→生成→删除远端文件）

- [ ] **Step 1: 写失败测试** `backend/tests/test_llm.py`

```python
import httpx
import pytest
from app.llm import TextLLM, with_retry


class FakeResponse:
    def __init__(self, content: str):
        self._content = content
    def raise_for_status(self): pass
    def json(self):
        return {"choices": [{"message": {"content": self._content}}]}


async def test_text_llm_generate(monkeypatch):
    captured = {}

    async def fake_post(self, url, headers=None, json=None):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        return FakeResponse("生成结果")

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    llm = TextLLM("https://api.example.com/v1", "sk-test", "test-model")
    out = await llm.generate("系统提示", "用户输入")
    assert out == "生成结果"
    assert captured["url"] == "https://api.example.com/v1/chat/completions"
    assert captured["json"]["model"] == "test-model"
    assert captured["json"]["messages"][0] == {"role": "system", "content": "系统提示"}
    assert captured["headers"]["Authorization"] == "Bearer sk-test"


async def test_with_retry_succeeds_after_failures():
    calls = {"n": 0}
    async def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("boom")
        return "ok"
    out = await with_retry(flaky, attempts=3, base_delay=0.01)
    assert out == "ok"
    assert calls["n"] == 3


async def test_with_retry_exhausted():
    async def always_fail():
        raise RuntimeError("boom")
    with pytest.raises(RuntimeError):
        await with_retry(always_fail, attempts=2, base_delay=0.01)
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_llm.py -v`
Expected: FAIL（ImportError）

- [ ] **Step 3: 实现** `backend/app/llm.py`

```python
import asyncio
import time
from pathlib import Path
from typing import Awaitable, Callable, TypeVar

import httpx

from app.config import AppConfig

T = TypeVar("T")


async def with_retry(fn: Callable[[], Awaitable[T]], attempts: int,
                     base_delay: float = 2.0) -> T:
    """指数退避重试。attempts 为总尝试次数。"""
    last: Exception | None = None
    for i in range(attempts):
        try:
            return await fn()
        except Exception as e:  # noqa: BLE001 - 对上游 API 错误统一重试
            last = e
            if i < attempts - 1:
                await asyncio.sleep(base_delay * (2 ** i))
    raise last  # type: ignore[misc]


class TextLLM:
    """OpenAI 兼容 chat/completions 客户端（DeepSeek/GPT/Kimi/Gemini-compat）。"""

    def __init__(self, base_url: str, api_key: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    async def generate(self, system: str, user: str,
                       temperature: float = 0.7) -> str:
        async with httpx.AsyncClient(timeout=600) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "temperature": temperature,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                },
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]


def make_text_llm(cfg: AppConfig) -> TextLLM:
    p = cfg.text_llm.active()
    return TextLLM(p.base_url, p.api_key, p.model)


class GeminiVideo:
    """Gemini 原生视频通道：Files API 上传 + 分析。SDK 为同步接口，用线程包装。"""

    UPLOAD_TIMEOUT = 600  # 等待文件 ACTIVE 的秒数上限

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    def _analyze_sync(self, video_path: Path, prompt: str) -> str:
        from google import genai

        client = genai.Client(api_key=self.api_key)
        f = client.files.upload(file=str(video_path))
        try:
            deadline = time.monotonic() + self.UPLOAD_TIMEOUT
            while f.state.name == "PROCESSING":
                if time.monotonic() > deadline:
                    raise TimeoutError(f"视频处理超时: {video_path.name}")
                time.sleep(5)
                f = client.files.get(name=f.name)
            if f.state.name != "ACTIVE":
                raise RuntimeError(f"视频处理失败({f.state.name}): {video_path.name}")
            resp = client.models.generate_content(
                model=self.model, contents=[f, prompt])
            return resp.text
        finally:
            try:
                client.files.delete(name=f.name)
            except Exception:
                pass  # 远端清理失败不影响结果

    async def analyze(self, video_path: Path, prompt: str) -> str:
        return await asyncio.to_thread(self._analyze_sync, video_path, prompt)
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_llm.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/llm.py backend/tests/test_llm.py
git commit -m "feat: LLM 适配层（TextLLM/GeminiVideo/重试）"
```

---

### Task 6: 五阶段 Prompt 与阶段①扒剧

**Files:**
- Create: `backend/app/prompts.py`, `backend/app/pipeline.py`, `backend/tests/test_pipeline.py`

**Interfaces:**
- Consumes: `GeminiVideo.analyze`、`with_retry`（Task 5）、`validate_script`（Task 2）、`ProjectStore`（Task 3）、`StatusDB`（Task 4）
- Produces:
  - `prompts.py` 常量：`STAGE1_EXTRACT`、`STAGE2_CHUNK_SUMMARY`、`STAGE2_REPORT`、`STAGE3_SUGGEST`、`STAGE3_REFINE`、`STAGE4_OUTLINE`、`STAGE5_SCRIPT`（均为含 `{占位符}` 的 str）
  - `split_stage1_output(text: str) -> tuple[str, dict]`（分离剧本正文与末尾 ```json 结构标注块；无 json 块时返回 `(text, {})`）
  - `async extract_episode(pid: str, ep: int, video_path: Path, gemini, store, db, attempts: int) -> None`（完成后写 `ep{NNN}.script.md` + `ep{NNN}.meta.json` 并置状态 done；失败置 failed 并记录 error，不抛异常）

- [ ] **Step 1: 实现 prompts** `backend/app/prompts.py`

```python
SCRIPT_FORMAT_RULES = """剧本格式规范（必须严格遵守）：
1. 每一场以场次头开始，独占一行：`集数-场号  时间  内/外  地点`
   示例：`1-4  夜  内  博物馆柜台`。场号从 1 开始连续递增。
2. 场次头下一行写`出场人物：`，列出本场出场人物，多个用顿号分隔；无人物写"无"。
3. 画面/动作描述行以 `▲ ` 开头，一个镜头动作一行，写清可拍摄的具体画面。
4. 屏幕字幕写 `【字幕：内容】`，特效/音效写 `【特效：内容】`。
5. 台词格式：`角色名(语气)：台词`。旁白配音用 `(vo)`，内心独白用 `(os)`，
   现场台词可标注情绪如 `(惊诧)`、`(冷笑)`，无特别情绪可省略括号。
6. 台词必须逐句完整记录，不得概括省略。"""

STAGE1_EXTRACT = f"""你是专业的短剧剧本记录员。请完整观看这段短剧视频（第{{episode}}集），
将其转写为标准短剧剧本。要求：
- 按镜头场景切分场次，本集集数为 {{episode}}，场号从 {{episode}}-1 开始。
- 逐句记录全部台词（含语气标注）、画面动作、屏幕字幕与特效。
- 不要遗漏任何情节，不要添加原视频中不存在的内容。

{SCRIPT_FORMAT_RULES}

剧本输出完毕后，另起一行输出一个 JSON 代码块（```json 包裹），标注本集结构：
{{{{"hooks": [{{{{"scene": 场号, "desc": "钩子描述"}}}}],
 "twists": [{{{{"scene": 场号, "desc": "反转描述"}}}}],
 "climaxes": [{{{{"scene": 场号, "desc": "爽点描述"}}}}],
 "characters": ["本集出场人物"],
 "summary": "本集剧情一句话概括"}}}}
"""

STAGE2_CHUNK_SUMMARY = """你是短剧编剧分析师。以下是某部短剧第{start}~{end}集的完整剧本。
请输出这一段的剧情摘要与结构分析，包含：
1. 分段剧情概述（按集）
2. 出场人物及关系变化
3. 每集的钩子、反转、爽点（标注集数）
4. 这一段在全剧中的功能（铺垫/升级/高潮等）

剧本内容：
{scripts}"""

STAGE2_REPORT = """你是资深短剧编剧顾问。基于以下材料，输出这部短剧的完整拆解报告（Markdown 格式），
必须包含以下章节：
# 一、基本信息（题材类型、总集数、目标受众）
# 二、人物设定与关系图谱（主要人物小传、关系与变化）
# 三、主线与支线结构（幕结构、关键转折点所在集数）
# 四、逐集节奏表（表格：集数 | 剧情概要 | 钩子 | 反转 | 爽点）
# 五、题材套路总结（该剧使用的核心套路、爽点类型、钩子技巧，可迁移到其他题材的结构规律）

材料：
{material}"""

STAGE3_SUGGEST = """你是短剧策划。以下是一部短剧的拆解报告。请基于其剧情结构，
提出 3 个可以复用该结构、但题材/背景/人物完全不同的新剧方向。
每个方向输出：题材名称、一句话卖点、主角设定、与原剧结构的对应关系（原剧核心设定→新剧对应设定）。

拆解报告：
{report}"""

STAGE3_REFINE = """你是短剧策划。基于原剧拆解报告和用户草拟的新剧设定，
补全为完整的新剧设定文档（Markdown），必须包含：
# 一、题材与一句话卖点
# 二、世界观设定
# 三、人物表（每个主要角色：姓名、身份、性格、目标）
# 四、新旧人物映射表（表格：原剧角色 | 新剧角色 | 结构功能说明）
保持用户已写内容不变，只补全缺失部分并润色。

原剧拆解报告：
{report}

用户草拟的新剧设定：
{draft}"""

STAGE4_OUTLINE = """你是短剧编剧。基于原剧拆解报告和新剧设定，为新剧编写逐集大纲。
总集数 {episode_count} 集，与原剧一一对应：每集保留原剧对应集的结构功能
（钩子位置、反转节奏、爽点类型），但剧情内容完全使用新剧的题材、人物、世界观。

输出格式（Markdown，每集一节）：
## 第N集（对应原剧第N集：<原剧该集结构功能一句话>）
- 剧情：本集剧情概要（3-5 句）
- 钩子：结尾钩子设计
- 爽点：本集爽点

原剧拆解报告：
{report}

新剧设定：
{settings}"""

STAGE5_SCRIPT = f"""你是专业短剧编剧。请为新剧编写第{{episode}}集完整剧本。

创作要求：
- 严格按照本集大纲展开剧情，使用新剧设定中的人物与世界观。
- 参考原剧第{{episode}}集剧本的场次数量、节奏密度、钩子/反转/爽点位置，
  做结构对齐，但剧情、人物、台词必须全部原创，不得出现原剧的人名、地名、台词。
- 与上一集结尾自然衔接。
- 台词口语化、有冲突感，符合短剧快节奏。
{{extra}}

{SCRIPT_FORMAT_RULES}

本集集数为 {{episode}}，场号从 {{episode}}-1 开始。只输出剧本正文，不要输出其他说明。

【新剧设定】
{{settings}}

【本集大纲】
{{outline_section}}

【上一集结尾（衔接参考）】
{{prev_ending}}

【原剧第{{episode}}集剧本（仅作结构节奏参照）】
{{original_script}}
"""
```

- [ ] **Step 2: 写失败测试** `backend/tests/test_pipeline.py`

```python
import json
from pathlib import Path

from app.db import StatusDB
from app.pipeline import extract_episode, split_stage1_output
from app.storage import ProjectStore

SCRIPT_BODY = """1-1  夜  外  门前
出场人物：张三

▲ 张三走进大门。
张三(vo)：我叫张三。
"""

GEMINI_OUTPUT = SCRIPT_BODY + """
```json
{"hooks": [{"scene": 1, "desc": "悬念开场"}], "twists": [], "climaxes": [],
 "characters": ["张三"], "summary": "张三入职"}
```
"""


def test_split_stage1_output():
    script, meta = split_stage1_output(GEMINI_OUTPUT)
    assert "张三(vo)：我叫张三。" in script
    assert "```json" not in script
    assert meta["hooks"][0]["desc"] == "悬念开场"

def test_split_without_json():
    script, meta = split_stage1_output(SCRIPT_BODY)
    assert script.strip() == SCRIPT_BODY.strip()
    assert meta == {}


class FakeGemini:
    def __init__(self, output=GEMINI_OUTPUT, fail_times=0):
        self.output = output
        self.fail_times = fail_times
        self.calls = 0
    async def analyze(self, video_path, prompt):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise RuntimeError("api error")
        return self.output


def make_env(tmp_path: Path):
    store = ProjectStore(tmp_path / "data")
    vd = tmp_path / "v"; vd.mkdir()
    (vd / "ep1.mp4").write_bytes(b"\x00")
    project = store.create_project("剧", str(vd))
    db = StatusDB(tmp_path / "status.db")
    return store, db, project, vd / "ep1.mp4"


async def test_extract_episode_success(tmp_path: Path):
    store, db, p, video = make_env(tmp_path)
    await extract_episode(p["id"], 1, video, FakeGemini(), store, db, attempts=1)
    assert db.get_statuses(p["id"])[1]["status"] == "done"
    script = store.read(store.episode_script_path(p["id"], 1))
    assert "张三(vo)：我叫张三。" in script
    meta = json.loads(store.read(store.episode_meta_path(p["id"], 1)))
    assert meta["structure"]["summary"] == "张三入职"

async def test_extract_episode_retry_then_success(tmp_path: Path):
    store, db, p, video = make_env(tmp_path)
    g = FakeGemini(fail_times=1)
    await extract_episode(p["id"], 1, video, g, store, db, attempts=3)
    assert g.calls == 2
    assert db.get_statuses(p["id"])[1]["status"] == "done"

async def test_extract_episode_failure_recorded(tmp_path: Path):
    store, db, p, video = make_env(tmp_path)
    await extract_episode(p["id"], 1, video, FakeGemini(fail_times=99),
                          store, db, attempts=2)
    s = db.get_statuses(p["id"])[1]
    assert s["status"] == "failed"
    assert "api error" in s["error"]

async def test_extract_episode_invalid_script_fails(tmp_path: Path):
    store, db, p, video = make_env(tmp_path)
    await extract_episode(p["id"], 1, video, FakeGemini(output="没有场次头的胡话"),
                          store, db, attempts=1)
    assert db.get_statuses(p["id"])[1]["status"] == "failed"
```

- [ ] **Step 3: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_pipeline.py -v`
Expected: FAIL（ImportError: pipeline）

- [ ] **Step 4: 实现 pipeline 阶段①** `backend/app/pipeline.py`

```python
import json
import re
from pathlib import Path

from app import prompts
from app.db import StatusDB
from app.llm import with_retry
from app.script_format import validate_script
from app.storage import ProjectStore

_JSON_BLOCK_RE = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)


def split_stage1_output(text: str) -> tuple[str, dict]:
    """分离 Gemini 输出中的剧本正文与末尾 JSON 结构标注。"""
    matches = list(_JSON_BLOCK_RE.finditer(text))
    if not matches:
        return text.strip(), {}
    last = matches[-1]
    script = (text[:last.start()] + text[last.end():]).strip()
    try:
        meta = json.loads(last.group(1))
    except json.JSONDecodeError:
        meta = {}
    return script, meta


async def extract_episode(pid: str, ep: int, video_path: Path,
                          gemini, store: ProjectStore, db: StatusDB,
                          attempts: int) -> None:
    """阶段①：扒一集。成功写 script+meta 并置 done；失败置 failed，不抛异常。"""

    async def _do() -> tuple[str, dict]:
        db.set_status(pid, ep, "uploading")
        prompt = prompts.STAGE1_EXTRACT.format(episode=ep)
        db.set_status(pid, ep, "analyzing")
        raw = await gemini.analyze(video_path, prompt)
        script, structure = split_stage1_output(raw)
        errors = validate_script(script, expected_episode=ep)
        if errors:
            raise ValueError("剧本格式校验失败: " + "; ".join(errors))
        return script, structure

    try:
        script, structure = await with_retry(_do, attempts=attempts)
    except Exception as e:  # noqa: BLE001 - 失败集记录错误，不中断批处理
        db.set_status(pid, ep, "failed", error=str(e))
        return

    store.write(store.episode_script_path(pid, ep), script)
    store.write(store.episode_meta_path(pid, ep),
                json.dumps({"episode": ep, "structure": structure},
                           ensure_ascii=False, indent=2))
    db.set_status(pid, ep, "done")
```

- [ ] **Step 5: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_pipeline.py -v`
Expected: 6 passed

- [ ] **Step 6: Commit**

```bash
git add backend/app/prompts.py backend/app/pipeline.py backend/tests/test_pipeline.py
git commit -m "feat: 五阶段 prompt 与阶段①扒剧"
```

---

### Task 7: 并发批处理引擎与事件总线

**Files:**
- Create: `backend/app/engine.py`, `backend/tests/test_engine.py`

**Interfaces:**
- Produces:
  - `class EventBus`：`subscribe(pid: str) -> asyncio.Queue`、`unsubscribe(pid: str, q) -> None`、`publish(pid: str, event: dict) -> None`（广播到该项目的所有订阅队列）
  - `class BatchRunner(concurrency: int, bus: EventBus)`：
    - `async start(pid: str, items: list[int], worker: Callable[[int], Awaitable[None]]) -> None`（后台启动，不阻塞；若该 pid 已在运行则抛 `RuntimeError`）
    - `is_running(pid: str) -> bool`
    - `cancel(pid: str) -> None`（暂停=取消未完成项；已完成的集保留在磁盘/DB，重新 start 即续跑）
    - 每个 item 完成后 `publish(pid, {"type": "item_done", "item": n})`；全部结束后 `publish(pid, {"type": "batch_done"})`
  - worker 自身负责失败处理（Task 6 的 `extract_episode` 不抛异常），Runner 仍捕获 worker 意外异常并继续其余项

- [ ] **Step 1: 写失败测试** `backend/tests/test_engine.py`

```python
import asyncio
import pytest
from app.engine import BatchRunner, EventBus


async def drain(q: asyncio.Queue) -> list[dict]:
    out = []
    while not q.empty():
        out.append(q.get_nowait())
    return out


async def test_batch_runs_all_items():
    bus = EventBus()
    q = bus.subscribe("p1")
    done: list[int] = []
    async def worker(n: int):
        await asyncio.sleep(0.01)
        done.append(n)
    runner = BatchRunner(concurrency=2, bus=bus)
    await runner.start("p1", [1, 2, 3], worker)
    assert runner.is_running("p1")
    while runner.is_running("p1"):
        await asyncio.sleep(0.01)
    assert sorted(done) == [1, 2, 3]
    events = await drain(q)
    assert {"type": "batch_done"} in events
    assert sum(1 for e in events if e["type"] == "item_done") == 3


async def test_concurrency_limit():
    bus = EventBus()
    active = {"now": 0, "max": 0}
    async def worker(n: int):
        active["now"] += 1
        active["max"] = max(active["max"], active["now"])
        await asyncio.sleep(0.03)
        active["now"] -= 1
    runner = BatchRunner(concurrency=2, bus=bus)
    await runner.start("p1", list(range(6)), worker)
    while runner.is_running("p1"):
        await asyncio.sleep(0.01)
    assert active["max"] <= 2


async def test_reject_double_start():
    bus = EventBus()
    async def worker(n: int):
        await asyncio.sleep(0.05)
    runner = BatchRunner(concurrency=1, bus=bus)
    await runner.start("p1", [1, 2], worker)
    with pytest.raises(RuntimeError):
        await runner.start("p1", [3], worker)
    runner.cancel("p1")


async def test_cancel_stops_pending():
    bus = EventBus()
    done: list[int] = []
    async def worker(n: int):
        await asyncio.sleep(0.05)
        done.append(n)
    runner = BatchRunner(concurrency=1, bus=bus)
    await runner.start("p1", [1, 2, 3, 4], worker)
    await asyncio.sleep(0.07)   # 让第 1 项完成
    runner.cancel("p1")
    await asyncio.sleep(0.05)
    assert not runner.is_running("p1")
    assert len(done) < 4


async def test_worker_exception_does_not_stop_batch():
    bus = EventBus()
    done: list[int] = []
    async def worker(n: int):
        if n == 2:
            raise RuntimeError("unexpected")
        done.append(n)
    runner = BatchRunner(concurrency=1, bus=bus)
    await runner.start("p1", [1, 2, 3], worker)
    while runner.is_running("p1"):
        await asyncio.sleep(0.01)
    assert done == [1, 3]
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_engine.py -v`
Expected: FAIL（ImportError）

- [ ] **Step 3: 实现** `backend/app/engine.py`

```python
import asyncio
from typing import Awaitable, Callable


class EventBus:
    """按项目 ID 广播事件，供 SSE 订阅。"""

    def __init__(self):
        self._subs: dict[str, list[asyncio.Queue]] = {}

    def subscribe(self, pid: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subs.setdefault(pid, []).append(q)
        return q

    def unsubscribe(self, pid: str, q: asyncio.Queue) -> None:
        if pid in self._subs and q in self._subs[pid]:
            self._subs[pid].remove(q)

    def publish(self, pid: str, event: dict) -> None:
        for q in self._subs.get(pid, []):
            q.put_nowait(event)


class BatchRunner:
    """带并发上限的批处理。每项目同时只允许一个批次。"""

    def __init__(self, concurrency: int, bus: EventBus):
        self.concurrency = concurrency
        self.bus = bus
        self._batches: dict[str, asyncio.Task] = {}

    def is_running(self, pid: str) -> bool:
        t = self._batches.get(pid)
        return t is not None and not t.done()

    async def start(self, pid: str, items: list[int],
                    worker: Callable[[int], Awaitable[None]]) -> None:
        if self.is_running(pid):
            raise RuntimeError(f"项目 {pid} 已有任务在运行")
        self._batches[pid] = asyncio.create_task(
            self._run(pid, items, worker))

    def cancel(self, pid: str) -> None:
        t = self._batches.get(pid)
        if t and not t.done():
            t.cancel()

    async def _run(self, pid: str, items: list[int],
                   worker: Callable[[int], Awaitable[None]]) -> None:
        sem = asyncio.Semaphore(self.concurrency)

        async def one(n: int) -> None:
            async with sem:
                try:
                    await worker(n)
                except asyncio.CancelledError:
                    raise
                except Exception:  # noqa: BLE001 - 单项意外失败不影响批次
                    pass
                self.bus.publish(pid, {"type": "item_done", "item": n})

        try:
            await asyncio.gather(*(one(n) for n in items))
        finally:
            self.bus.publish(pid, {"type": "batch_done"})
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_engine.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/engine.py backend/tests/test_engine.py
git commit -m "feat: 并发批处理引擎与事件总线"
```

---

### Task 8: 阶段②~⑤流水线函数

**Files:**
- Modify: `backend/app/pipeline.py`（追加函数）
- Test: `backend/tests/test_pipeline.py`（追加测试）

**Interfaces:**
- Consumes: `TextLLM.generate(system, user, temperature)`（Task 5）、`prompts`（Task 6）
- Produces（全部追加到 `app/pipeline.py`）：
  - `chunk_list(items: list, size: int) -> list[list]`
  - `async generate_report(scripts: list[tuple[int, str]], llm, chunk_size: int = 20) -> str`（≤chunk_size 集直接生成；否则先分段摘要再汇总）
  - `async suggest_themes(report: str, llm) -> str`
  - `async refine_settings(report: str, draft: str, llm) -> str`
  - `async generate_outline(report: str, settings: str, episode_count: int, llm) -> str`
  - `extract_outline_section(outline: str, ep: int) -> str`（从大纲 Markdown 中截取 `## 第N集` 小节；找不到返回全文）
  - `async generate_new_episode(ep: int, original_script: str, outline_section: str, settings: str, prev_ending: str, extra: str, llm) -> str`
  - `tail_lines(text: str, n: int = 30) -> str`（取末尾 n 行，用作上一集结尾衔接）
  - 系统提示常量 `SYSTEM_WRITER = "你是资深短剧编剧，精通竖屏短剧的节奏与钩子设计。"`

- [ ] **Step 1: 追加失败测试**（追加到 `backend/tests/test_pipeline.py` 末尾）

```python
from app.pipeline import (chunk_list, extract_outline_section, generate_report,
                          generate_new_episode, tail_lines)


class FakeLLM:
    def __init__(self):
        self.calls: list[str] = []   # 记录每次 user prompt
    async def generate(self, system, user, temperature=0.7):
        self.calls.append(user)
        return f"[输出{len(self.calls)}]"


def test_chunk_list():
    assert chunk_list([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]
    assert chunk_list([], 2) == []

def test_tail_lines():
    text = "\n".join(str(i) for i in range(50))
    out = tail_lines(text, 3)
    assert out == "47\n48\n49"

def test_extract_outline_section():
    outline = "## 第1集（对应原剧第1集）\n- 剧情：A\n\n## 第2集（xx）\n- 剧情：B\n\n## 第3集\n- 剧情：C"
    sec = extract_outline_section(outline, 2)
    assert "剧情：B" in sec and "剧情：C" not in sec
    assert extract_outline_section("无小节", 1) == "无小节"

async def test_generate_report_small():
    llm = FakeLLM()
    scripts = [(1, "剧本一"), (2, "剧本二")]
    out = await generate_report(scripts, llm, chunk_size=20)
    assert out == "[输出1]"
    assert len(llm.calls) == 1
    assert "剧本一" in llm.calls[0]

async def test_generate_report_chunked():
    llm = FakeLLM()
    scripts = [(i, f"剧本{i}") for i in range(1, 6)]
    out = await generate_report(scripts, llm, chunk_size=2)
    # 5 集 / 每段 2 集 = 3 段摘要 + 1 次汇总 = 4 次调用
    assert len(llm.calls) == 4
    assert out == "[输出4]"

async def test_generate_new_episode_prompt_contains_inputs():
    llm = FakeLLM()
    out = await generate_new_episode(
        ep=3, original_script="原剧本内容", outline_section="本集大纲内容",
        settings="设定内容", prev_ending="上集结尾", extra="台词更口语化", llm=llm)
    assert out == "[输出1]"
    u = llm.calls[0]
    for piece in ["原剧本内容", "本集大纲内容", "设定内容", "上集结尾", "台词更口语化"]:
        assert piece in u
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_pipeline.py -v`
Expected: 新增测试 FAIL（ImportError: chunk_list 等）

- [ ] **Step 3: 实现**（追加到 `backend/app/pipeline.py` 末尾）

```python
SYSTEM_WRITER = "你是资深短剧编剧，精通竖屏短剧的节奏与钩子设计。"


def chunk_list(items: list, size: int) -> list[list]:
    return [items[i:i + size] for i in range(0, len(items), size)]


def tail_lines(text: str, n: int = 30) -> str:
    return "\n".join(text.splitlines()[-n:])


def _join_scripts(scripts: list[tuple[int, str]]) -> str:
    return "\n\n".join(f"=== 第{ep}集 ===\n{body}" for ep, body in scripts)


async def generate_report(scripts: list[tuple[int, str]], llm,
                          chunk_size: int = 20) -> str:
    """阶段②：全剧拆解。集数多时先分段摘要再汇总。"""
    if len(scripts) <= chunk_size:
        material = _join_scripts(scripts)
    else:
        summaries = []
        for chunk in chunk_list(scripts, chunk_size):
            user = prompts.STAGE2_CHUNK_SUMMARY.format(
                start=chunk[0][0], end=chunk[-1][0],
                scripts=_join_scripts(chunk))
            summaries.append(await llm.generate(SYSTEM_WRITER, user))
        material = "\n\n".join(summaries)
    user = prompts.STAGE2_REPORT.format(material=material)
    return await llm.generate(SYSTEM_WRITER, user)


async def suggest_themes(report: str, llm) -> str:
    return await llm.generate(
        SYSTEM_WRITER, prompts.STAGE3_SUGGEST.format(report=report))


async def refine_settings(report: str, draft: str, llm) -> str:
    return await llm.generate(
        SYSTEM_WRITER, prompts.STAGE3_REFINE.format(report=report, draft=draft))


async def generate_outline(report: str, settings: str,
                           episode_count: int, llm) -> str:
    return await llm.generate(
        SYSTEM_WRITER,
        prompts.STAGE4_OUTLINE.format(
            report=report, settings=settings, episode_count=episode_count))


def extract_outline_section(outline: str, ep: int) -> str:
    """截取大纲中 `## 第N集` 小节；找不到则返回全文。"""
    lines = outline.splitlines()
    start = end = None
    header = re.compile(rf"^##\s*第{ep}集")
    any_header = re.compile(r"^##\s*第\d+集")
    for i, line in enumerate(lines):
        if start is None and header.match(line.strip()):
            start = i
        elif start is not None and any_header.match(line.strip()):
            end = i
            break
    if start is None:
        return outline
    return "\n".join(lines[start:end]).strip()


async def generate_new_episode(ep: int, original_script: str,
                               outline_section: str, settings: str,
                               prev_ending: str, extra: str, llm) -> str:
    extra_line = f"- 额外要求：{extra}" if extra else ""
    user = prompts.STAGE5_SCRIPT.format(
        episode=ep, settings=settings, outline_section=outline_section,
        prev_ending=prev_ending or "（本集为第一集，无上一集）",
        original_script=original_script, extra=extra_line)
    return await llm.generate(SYSTEM_WRITER, user)
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_pipeline.py -v`
Expected: 全部通过（Task 6 的 6 个 + 新增 6 个 = 12 passed）

- [ ] **Step 5: Commit**

```bash
git add backend/app/pipeline.py backend/tests/test_pipeline.py
git commit -m "feat: 阶段②~⑤流水线函数"
```

---

### Task 9: 全剧汇总导出

**Files:**
- Create: `backend/app/export.py`, `backend/tests/test_export.py`

**Interfaces:**
- Produces: `export_full(title: str, scripts: dict[int, str | None]) -> str`
  - `scripts` 键为集数，值为剧本文本（缺失/失败的集为 None）
  - 输出参考格式：标题行 + 基本信息（总集数/成功/失败/生成时间）+ 目录 + 逐集正文；失败的集在正文处标注 `（本集缺失）`

- [ ] **Step 1: 写失败测试** `backend/tests/test_export.py`

```python
from app.export import export_full

def test_export_full():
    out = export_full("测试剧", {1: "第一集剧本内容", 2: None, 3: "第三集剧本内容"})
    assert out.startswith("《测试剧》全剧剧本汇总")
    assert "- 总集数:3" in out
    assert "- 成功:2 集 / 失败:1 集" in out
    assert "- [第1集](#第1集)" in out
    assert "第一集剧本内容" in out
    assert "（本集缺失）" in out
    # 目录在正文之前
    assert out.index("- [第3集]") < out.index("第三集剧本内容")
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_export.py -v`
Expected: FAIL（ImportError）

- [ ] **Step 3: 实现** `backend/app/export.py`

```python
from datetime import date


def export_full(title: str, scripts: dict[int, str | None]) -> str:
    eps = sorted(scripts)
    ok = sum(1 for e in eps if scripts[e])
    parts = [
        f"《{title}》全剧剧本汇总", "",
        "基本信息", "",
        f"- 总集数:{len(eps)}",
        f"- 成功:{ok} 集 / 失败:{len(eps) - ok} 集",
        f"- 生成时间:{date.today().isoformat()}", "",
        "目录", "",
    ]
    parts += [f"- [第{e}集](#第{e}集)" for e in eps]
    for e in eps:
        parts += ["", f"第{e}集", "", scripts[e] or "（本集缺失）"]
    return "\n".join(parts)
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_export.py -v`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/export.py backend/tests/test_export.py
git commit -m "feat: 全剧汇总导出"
```

---

### Task 10: HTTP API（路由 + SSE）

**Files:**
- Create: `backend/app/api.py`, `backend/app/main.py`, `backend/tests/conftest.py`, `backend/tests/test_api.py`

**Interfaces:**
- Consumes: 前面全部模块
- Produces: `create_app(cfg: AppConfig, gemini=None, text_llm=None) -> FastAPI`（gemini/text_llm 参数用于测试注入，None 时按配置真实创建）。`app.state` 挂载：`store`、`db`、`bus`、`runner`、`gemini`、`text_llm`、`cfg`

**路由清单（全部以 `/api` 为前缀）：**

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/projects` | body `{name, video_dir}` → 创建项目（扫描分集） |
| GET | `/projects` | 项目列表 |
| GET | `/projects/{pid}` | 项目详情 + 每集状态（合并 StatusDB） |
| PUT | `/projects/{pid}/episodes-mapping` | body `{episodes: [{episode, file}]}` 手动调整集数对应 |
| POST | `/projects/{pid}/stage1/start` | body `{episodes?: [int]}` 省略=所有未 done 的集；启动扒剧批次；已在运行返回 409 |
| POST | `/projects/{pid}/stage1/cancel` | 暂停批次 |
| GET | `/projects/{pid}/episodes/{ep}/script` | 原剧剧本内容 `{content}`；不存在 404 |
| PUT | `/projects/{pid}/episodes/{ep}/script` | body `{content}` 保存人工编辑 |
| POST | `/projects/{pid}/stage2/generate` | 生成拆解报告（同步等待 LLM，写 analysis/report.md） |
| POST | `/projects/{pid}/stage3/suggest` | 返回 `{content}` 新题材建议（不落盘） |
| POST | `/projects/{pid}/stage3/refine` | body `{draft}` → AI 完善设定，写 settings/new_drama.md |
| POST | `/projects/{pid}/stage4/generate` | 生成大纲，写 outline/outline.md |
| POST | `/projects/{pid}/stage5/generate` | body `{episode, extra?}` 生成单集新剧本，写 scripts/epNNN.md |
| POST | `/projects/{pid}/stage5/start` | body `{episodes?, extra?}` 批量生成新剧本（复用 BatchRunner） |
| GET/PUT | `/projects/{pid}/artifacts/{kind}` | kind ∈ analysis/settings/outline，读写产物 `{content}` |
| GET/PUT | `/projects/{pid}/scripts/{ep}` | 新剧单集剧本读写 `{content}` |
| GET | `/projects/{pid}/export?which=original\|new` | 全剧汇总文本（text/plain） |
| GET | `/projects/{pid}/events` | SSE 事件流 |

- [ ] **Step 1: 写 conftest** `backend/tests/conftest.py`

```python
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import AppConfig
from app.main import create_app

CFG = {
    "gemini": {"api_key": "gk", "model": "m"},
    "text_llm": {"provider": "fake",
                 "providers": {"fake": {"base_url": "http://x", "api_key": "k",
                                        "model": "m"}}},
    "concurrency": 2, "retries": 1,
}

GEMINI_OUTPUT_TPL = """{ep}-1  夜  内  房间
出场人物：主角

▲ 主角出场。
主角(vo)：第{ep}集开场。

```json
{{"hooks": [], "twists": [], "climaxes": [], "characters": ["主角"], "summary": "第{ep}集"}}
```
"""


class FakeGemini:
    async def analyze(self, video_path, prompt):
        import re
        ep = int(re.search(r"第(\d+)集", prompt).group(1))
        return GEMINI_OUTPUT_TPL.format(ep=ep)


class FakeTextLLM:
    async def generate(self, system, user, temperature=0.7):
        return "模拟LLM输出"


@pytest.fixture
def video_dir(tmp_path: Path) -> Path:
    vd = tmp_path / "videos"
    vd.mkdir()
    for i in (1, 2):
        (vd / f"第{i}集.mp4").write_bytes(b"\x00")
    return vd


@pytest.fixture
async def client(tmp_path: Path):
    cfg = AppConfig.model_validate({**CFG, "data_dir": str(tmp_path / "data")})
    app = create_app(cfg, gemini=FakeGemini(), text_llm=FakeTextLLM())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        yield c
```

- [ ] **Step 2: 写失败测试** `backend/tests/test_api.py`

```python
import asyncio


async def create_project(client, video_dir) -> str:
    r = await client.post("/api/projects",
                          json={"name": "测试剧", "video_dir": str(video_dir)})
    assert r.status_code == 200
    return r.json()["id"]


async def wait_stage1(client, pid):
    for _ in range(100):
        r = await client.get(f"/api/projects/{pid}")
        eps = r.json()["episodes"]
        if all(e["status"] in ("done", "failed") for e in eps):
            return eps
        await asyncio.sleep(0.05)
    raise TimeoutError


async def test_project_crud(client, video_dir):
    pid = await create_project(client, video_dir)
    r = await client.get("/api/projects")
    assert [p["id"] for p in r.json()] == [pid]
    r = await client.get(f"/api/projects/{pid}")
    body = r.json()
    assert body["name"] == "测试剧"
    assert [e["episode"] for e in body["episodes"]] == [1, 2]
    assert all(e["status"] == "pending" for e in body["episodes"])


async def test_stage1_and_script_io(client, video_dir):
    pid = await create_project(client, video_dir)
    r = await client.post(f"/api/projects/{pid}/stage1/start", json={})
    assert r.status_code == 200
    eps = await wait_stage1(client, pid)
    assert all(e["status"] == "done" for e in eps)
    r = await client.get(f"/api/projects/{pid}/episodes/1/script")
    assert "第1集开场" in r.json()["content"]
    r = await client.put(f"/api/projects/{pid}/episodes/1/script",
                         json={"content": "人工修改后的剧本"})
    assert r.status_code == 200
    r = await client.get(f"/api/projects/{pid}/episodes/1/script")
    assert r.json()["content"] == "人工修改后的剧本"


async def test_stage2_to_5_flow(client, video_dir):
    pid = await create_project(client, video_dir)
    await client.post(f"/api/projects/{pid}/stage1/start", json={})
    await wait_stage1(client, pid)

    r = await client.post(f"/api/projects/{pid}/stage2/generate")
    assert r.status_code == 200
    r = await client.get(f"/api/projects/{pid}/artifacts/analysis")
    assert r.json()["content"] == "模拟LLM输出"

    r = await client.post(f"/api/projects/{pid}/stage3/suggest")
    assert r.json()["content"] == "模拟LLM输出"
    r = await client.post(f"/api/projects/{pid}/stage3/refine",
                          json={"draft": "我的草稿"})
    assert r.status_code == 200

    r = await client.post(f"/api/projects/{pid}/stage4/generate")
    assert r.status_code == 200

    r = await client.post(f"/api/projects/{pid}/stage5/generate",
                          json={"episode": 1})
    assert r.status_code == 200
    r = await client.get(f"/api/projects/{pid}/scripts/1")
    assert r.json()["content"] == "模拟LLM输出"

    r = await client.get(f"/api/projects/{pid}/export", params={"which": "new"})
    assert "全剧剧本汇总" in r.text


async def test_stage2_requires_episodes(client, video_dir):
    pid = await create_project(client, video_dir)
    r = await client.post(f"/api/projects/{pid}/stage2/generate")
    assert r.status_code == 400   # 还没有任何已扒的剧本


async def test_missing_resources(client, video_dir):
    pid = await create_project(client, video_dir)
    r = await client.get(f"/api/projects/{pid}/episodes/1/script")
    assert r.status_code == 404
    r = await client.get("/api/projects/nonexist")
    assert r.status_code == 404
```

- [ ] **Step 3: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_api.py -v`
Expected: FAIL（ImportError: app.main）

- [ ] **Step 4: 实现** `backend/app/api.py`

```python
import asyncio
import json

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel

from app import pipeline
from app.export import export_full
from app.pipeline import extract_episode

router = APIRouter(prefix="/api")


# ---------- 请求模型 ----------

class ProjectIn(BaseModel):
    name: str
    video_dir: str

class EpisodesMappingIn(BaseModel):
    episodes: list[dict]

class Stage1In(BaseModel):
    episodes: list[int] | None = None

class ContentIn(BaseModel):
    content: str

class DraftIn(BaseModel):
    draft: str

class Stage5In(BaseModel):
    episode: int
    extra: str = ""

class Stage5BatchIn(BaseModel):
    episodes: list[int] | None = None
    extra: str = ""


# ---------- 辅助 ----------

def _project_or_404(req: Request, pid: str) -> dict:
    try:
        return req.app.state.store.get_project(pid)
    except FileNotFoundError:
        raise HTTPException(404, "项目不存在")

def _episodes_with_status(req: Request, project: dict) -> list[dict]:
    statuses = req.app.state.db.get_statuses(project["id"])
    out = []
    for e in project["episodes"]:
        s = statuses.get(e["episode"], {"status": "pending", "error": ""})
        out.append({**e, **s})
    return out

def _done_scripts(req: Request, project: dict) -> list[tuple[int, str]]:
    store = req.app.state.store
    out = []
    for e in project["episodes"]:
        text = store.read(store.episode_script_path(project["id"], e["episode"]))
        if text:
            out.append((e["episode"], text))
    return out

def _require_artifact(req: Request, pid: str, kind: str) -> str:
    store = req.app.state.store
    text = store.read(store.artifact_path(pid, kind))
    if not text:
        names = {"analysis": "拆解报告", "settings": "新剧设定", "outline": "大纲"}
        raise HTTPException(400, f"请先生成{names[kind]}")
    return text


# ---------- 项目 ----------

@router.post("/projects")
def create_project(body: ProjectIn, req: Request):
    return req.app.state.store.create_project(body.name, body.video_dir)

@router.get("/projects")
def list_projects(req: Request):
    return req.app.state.store.list_projects()

@router.get("/projects/{pid}")
def get_project(pid: str, req: Request):
    p = _project_or_404(req, pid)
    return {**p, "episodes": _episodes_with_status(req, p),
            "running": req.app.state.runner.is_running(pid)}

@router.put("/projects/{pid}/episodes-mapping")
def update_mapping(pid: str, body: EpisodesMappingIn, req: Request):
    p = _project_or_404(req, pid)
    p["episodes"] = body.episodes
    req.app.state.store.save_project(p)
    return {"ok": True}


# ---------- 阶段①扒剧 ----------

@router.post("/projects/{pid}/stage1/start")
async def stage1_start(pid: str, body: Stage1In, req: Request):
    st = req.app.state
    p = _project_or_404(req, pid)
    statuses = st.db.get_statuses(pid)
    targets = body.episodes or [
        e["episode"] for e in p["episodes"]
        if statuses.get(e["episode"], {}).get("status") != "done"]
    file_by_ep = {e["episode"]: e["file"] for e in p["episodes"]}
    from pathlib import Path
    video_dir = Path(p["video_dir"])

    async def worker(ep: int) -> None:
        await extract_episode(pid, ep, video_dir / file_by_ep[ep],
                              st.gemini, st.store, st.db,
                              attempts=st.cfg.retries + 1)

    for ep in targets:
        st.db.set_status(pid, ep, "pending")
    try:
        await st.runner.start(pid, targets, worker)
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    return {"started": targets}

@router.post("/projects/{pid}/stage1/cancel")
def stage1_cancel(pid: str, req: Request):
    req.app.state.runner.cancel(pid)
    return {"ok": True}


# ---------- 原剧剧本读写 ----------

@router.get("/projects/{pid}/episodes/{ep}/script")
def get_episode_script(pid: str, ep: int, req: Request):
    store = req.app.state.store
    text = store.read(store.episode_script_path(pid, ep))
    if text is None:
        raise HTTPException(404, "该集剧本不存在")
    return {"content": text}

@router.put("/projects/{pid}/episodes/{ep}/script")
def put_episode_script(pid: str, ep: int, body: ContentIn, req: Request):
    store = req.app.state.store
    store.write(store.episode_script_path(pid, ep), body.content)
    return {"ok": True}


# ---------- 阶段②~④ ----------

@router.post("/projects/{pid}/stage2/generate")
async def stage2_generate(pid: str, req: Request):
    st = req.app.state
    p = _project_or_404(req, pid)
    scripts = _done_scripts(req, p)
    if not scripts:
        raise HTTPException(400, "还没有已完成的扒剧剧本")
    report = await pipeline.generate_report(scripts, st.text_llm)
    st.store.write(st.store.artifact_path(pid, "analysis"), report)
    return {"content": report}

@router.post("/projects/{pid}/stage3/suggest")
async def stage3_suggest(pid: str, req: Request):
    st = req.app.state
    _project_or_404(req, pid)
    report = _require_artifact(req, pid, "analysis")
    return {"content": await pipeline.suggest_themes(report, st.text_llm)}

@router.post("/projects/{pid}/stage3/refine")
async def stage3_refine(pid: str, body: DraftIn, req: Request):
    st = req.app.state
    _project_or_404(req, pid)
    report = _require_artifact(req, pid, "analysis")
    settings = await pipeline.refine_settings(report, body.draft, st.text_llm)
    st.store.write(st.store.artifact_path(pid, "settings"), settings)
    return {"content": settings}

@router.post("/projects/{pid}/stage4/generate")
async def stage4_generate(pid: str, req: Request):
    st = req.app.state
    p = _project_or_404(req, pid)
    report = _require_artifact(req, pid, "analysis")
    settings = _require_artifact(req, pid, "settings")
    outline = await pipeline.generate_outline(
        report, settings, episode_count=len(p["episodes"]), llm=st.text_llm)
    st.store.write(st.store.artifact_path(pid, "outline"), outline)
    return {"content": outline}


# ---------- 阶段⑤ ----------

async def _gen_one_new_episode(st, pid: str, ep: int, extra: str) -> str:
    store = st.store
    settings = store.read(store.artifact_path(pid, "settings")) or ""
    outline = store.read(store.artifact_path(pid, "outline")) or ""
    if not settings or not outline:
        raise HTTPException(400, "请先完成新剧设定与大纲")
    original = store.read(store.episode_script_path(pid, ep)) or ""
    prev = store.read(store.new_script_path(pid, ep - 1)) if ep > 1 else None
    text = await pipeline.generate_new_episode(
        ep=ep, original_script=original,
        outline_section=pipeline.extract_outline_section(outline, ep),
        settings=settings,
        prev_ending=pipeline.tail_lines(prev) if prev else "",
        extra=extra, llm=st.text_llm)
    store.write(store.new_script_path(pid, ep), text)
    return text

@router.post("/projects/{pid}/stage5/generate")
async def stage5_generate(pid: str, body: Stage5In, req: Request):
    _project_or_404(req, pid)
    text = await _gen_one_new_episode(req.app.state, pid, body.episode, body.extra)
    return {"content": text}

@router.post("/projects/{pid}/stage5/start")
async def stage5_start(pid: str, body: Stage5BatchIn, req: Request):
    st = req.app.state
    p = _project_or_404(req, pid)
    targets = body.episodes or [e["episode"] for e in p["episodes"]]

    async def worker(ep: int) -> None:
        await _gen_one_new_episode(st, pid, ep, body.extra)

    try:
        await st.runner.start(pid, targets, worker)
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    return {"started": targets}


# ---------- 产物读写与导出 ----------

@router.get("/projects/{pid}/artifacts/{kind}")
def get_artifact(pid: str, kind: str, req: Request):
    store = req.app.state.store
    if kind not in ("analysis", "settings", "outline"):
        raise HTTPException(404, "未知产物类型")
    text = store.read(store.artifact_path(pid, kind))
    if text is None:
        raise HTTPException(404, "尚未生成")
    return {"content": text}

@router.put("/projects/{pid}/artifacts/{kind}")
def put_artifact(pid: str, kind: str, body: ContentIn, req: Request):
    store = req.app.state.store
    if kind not in ("analysis", "settings", "outline"):
        raise HTTPException(404, "未知产物类型")
    store.write(store.artifact_path(pid, kind), body.content)
    return {"ok": True}

@router.get("/projects/{pid}/scripts/{ep}")
def get_new_script(pid: str, ep: int, req: Request):
    store = req.app.state.store
    text = store.read(store.new_script_path(pid, ep))
    if text is None:
        raise HTTPException(404, "该集新剧本不存在")
    return {"content": text}

@router.put("/projects/{pid}/scripts/{ep}")
def put_new_script(pid: str, ep: int, body: ContentIn, req: Request):
    store = req.app.state.store
    store.write(store.new_script_path(pid, ep), body.content)
    return {"ok": True}

@router.get("/projects/{pid}/export")
def export(pid: str, which: str, req: Request):
    store = req.app.state.store
    p = _project_or_404(req, pid)
    path_fn = (store.episode_script_path if which == "original"
               else store.new_script_path)
    scripts = {e["episode"]: store.read(path_fn(pid, e["episode"]))
               for e in p["episodes"]}
    return PlainTextResponse(export_full(p["name"], scripts))


# ---------- SSE ----------

@router.get("/projects/{pid}/events")
async def events(pid: str, req: Request):
    bus = req.app.state.bus
    q = bus.subscribe(pid)

    async def stream():
        try:
            while True:
                if await req.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(q.get(), timeout=15)
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            bus.unsubscribe(pid, q)

    return StreamingResponse(stream(), media_type="text/event-stream")
```

- [ ] **Step 5: 实现** `backend/app/main.py`

```python
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router
from app.config import AppConfig, load_config
from app.db import StatusDB
from app.engine import BatchRunner, EventBus
from app.llm import GeminiVideo, make_text_llm
from app.storage import ProjectStore


def create_app(cfg: AppConfig, gemini=None, text_llm=None) -> FastAPI:
    app = FastAPI(title="短剧扒剧与仿写")
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"],
        allow_methods=["*"], allow_headers=["*"])
    data_dir = Path(cfg.data_dir)
    app.state.cfg = cfg
    app.state.store = ProjectStore(data_dir)
    app.state.db = StatusDB(data_dir / "status.db")
    app.state.bus = EventBus()
    app.state.runner = BatchRunner(cfg.concurrency, app.state.bus)
    app.state.gemini = gemini or GeminiVideo(cfg.gemini.api_key, cfg.gemini.model)
    app.state.text_llm = text_llm or make_text_llm(cfg)
    app.include_router(router)
    return app


def run() -> None:
    import uvicorn
    uvicorn.run(create_app(load_config()), host="127.0.0.1", port=8000)


if __name__ == "__main__":
    run()
```

注意：`ProjectStore.get_project` 在项目不存在时抛 `FileNotFoundError`（`read_text` 天然行为），`api.py` 已按此处理。

- [ ] **Step 6: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_api.py -v`
Expected: 5 passed

- [ ] **Step 7: 全量回归**

Run: `cd backend && python -m pytest tests/ -v`
Expected: 全部通过（约 27 个）

- [ ] **Step 8: Commit**

```bash
git add backend/app/api.py backend/app/main.py backend/tests/conftest.py backend/tests/test_api.py
git commit -m "feat: HTTP API 与 SSE"
```

---

### Task 11: 启动入口验证与真实视频冒烟测试

**Files:**
- Create: `backend/README.md`

- [ ] **Step 1: 写 README** `backend/README.md`

````markdown
# 短剧扒剧与仿写 — 后端

## 安装

```bash
cd backend
pip install -r requirements.txt
cp config.yaml.example config.yaml   # 填入真实 API key
```

## 运行

```bash
cd backend
python -m app.main
# API 文档: http://127.0.0.1:8000/docs
```

## 冒烟测试（需真实 Gemini key 与一个短视频）

```bash
# 1. 创建项目（video_dir 指向含 1 个短视频的目录）
curl -X POST http://127.0.0.1:8000/api/projects \
  -H "Content-Type: application/json" \
  -d '{"name": "冒烟测试", "video_dir": "D:/test_videos"}'

# 2. 启动扒剧（用返回的项目 id）
curl -X POST http://127.0.0.1:8000/api/projects/<pid>/stage1/start -H "Content-Type: application/json" -d '{}'

# 3. 查看进度
curl http://127.0.0.1:8000/api/projects/<pid>

# 4. 查看扒出的剧本
curl http://127.0.0.1:8000/api/projects/<pid>/episodes/1/script
```

## 测试

```bash
cd backend && python -m pytest tests/ -v
```
````

- [ ] **Step 2: 启动验证**

Run: `cd backend && python -c "from app.main import create_app; from app.config import AppConfig; create_app(AppConfig.model_validate({'gemini':{'api_key':'x'},'text_llm':{'provider':'p','providers':{'p':{'base_url':'http://x','api_key':'k','model':'m'}}}})); print('OK')"`
Expected: 输出 `OK`

- [ ] **Step 3: 冒烟测试（人工步骤，需要用户提供真实 key 与视频）**

按 README 的冒烟测试步骤，用一个真实短视频跑通阶段①，人工确认扒出的剧本格式正确。此步骤需要用户配合，不阻塞提交。

- [ ] **Step 4: Commit 并推送**

```bash
git add backend/README.md
git commit -m "docs: 后端 README 与冒烟测试指引"
git push
```

---

## Self-Review 记录

- **Spec 覆盖**：阶段①~⑤（Task 6/8/10）、剧本格式（Task 2）、数据目录（Task 3）、断点续跑与状态持久化（Task 4/7/10）、并发与重试（Task 5/7）、分段摘要（Task 8）、导出（Task 9）、SSE（Task 10）均有对应任务。前端界面在计划 2。
- **简化说明**（相对 spec 的两处收窄，已确认合理）：① ffprobe 元信息校验省略——Gemini 上传失败时错误路径相同，YAGNI；② 阶段②~⑤为短任务，状态不入 SQLite，重启后用户重新触发即可；SQLite 仅存阶段①逐集状态。
- **类型一致性**：`extract_episode/BatchRunner.start/create_app` 等签名在 Task 6/7/10 间已核对一致。




