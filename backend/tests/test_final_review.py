"""终审修复的回归测试：阶段⑤串行、失败可见性、pid 校验、409 前置检查。"""
import asyncio
import re
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import AppConfig
from app.engine import BatchRunner, EventBus
from app.main import create_app
from conftest import CFG, FakeGemini, FakeTextLLM


@pytest.fixture
def make_client(tmp_path: Path):
    @asynccontextmanager
    async def _make(gemini=None, text_llm=None):
        cfg = AppConfig.model_validate({**CFG, "data_dir": str(tmp_path / "data")})
        app = create_app(cfg, gemini=gemini or FakeGemini(),
                         text_llm=text_llm or FakeTextLLM())
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://t") as c:
            yield c
    return _make


def _make_videos(tmp_path: Path, n: int) -> Path:
    vd = tmp_path / "videos"
    vd.mkdir(exist_ok=True)
    for i in range(1, n + 1):
        (vd / f"第{i}集.mp4").write_bytes(b"\x00")
    return vd


async def _create_project(client, video_dir) -> str:
    r = await client.post("/api/projects",
                          json={"name": "测试剧", "video_dir": str(video_dir)})
    assert r.status_code == 200
    return r.json()["id"]


async def _wait_not_running(client, pid: str) -> None:
    for _ in range(200):
        r = await client.get(f"/api/projects/{pid}")
        if not r.json()["running"]:
            return
        await asyncio.sleep(0.02)
    raise TimeoutError


# ---------- Finding 1: 阶段⑤批量必须按集串行，保证前一集结尾进入提示词 ----------

class Stage5RecordingLLM:
    def __init__(self):
        self.calls: list[tuple[int, str]] = []

    async def generate(self, system, user, temperature=0.7):
        ep = int(re.search(r"编写第(\d+)集完整剧本", user).group(1))
        await asyncio.sleep(0.02)   # 让并发（若存在）真正交错
        self.calls.append((ep, user))
        return f"新剧本第{ep}集正文\nENDING-EP{ep}"


async def test_stage5_batch_sequential_continuity(make_client, tmp_path):
    llm = Stage5RecordingLLM()
    async with make_client(text_llm=llm) as client:
        vd = _make_videos(tmp_path, 3)
        pid = await _create_project(client, vd)
        for kind in ("settings", "outline"):
            r = await client.put(f"/api/projects/{pid}/artifacts/{kind}",
                                 json={"content": f"{kind}内容"})
            assert r.status_code == 200
        r = await client.post(f"/api/projects/{pid}/stage5/start", json={})
        assert r.status_code == 200
        await _wait_not_running(client, pid)

        order = [ep for ep, _ in llm.calls]
        assert order == [1, 2, 3]
        prompts = dict(llm.calls)
        assert "ENDING-EP1" in prompts[2]
        assert "ENDING-EP2" in prompts[3]


# ---------- Finding 2: 阶段⑤失败必须可见 ----------

async def test_stage5_start_requires_settings_and_outline(make_client, tmp_path):
    async with make_client() as client:
        vd = _make_videos(tmp_path, 2)
        pid = await _create_project(client, vd)
        r = await client.post(f"/api/projects/{pid}/stage5/start", json={})
        assert r.status_code == 400


async def test_batch_item_done_carries_failure():
    bus = EventBus()
    q = bus.subscribe("p1")

    async def worker(n: int):
        if n == 2:
            raise RuntimeError("boom")

    runner = BatchRunner(concurrency=1, bus=bus)
    await runner.start("p1", [1, 2], worker)
    while runner.is_running("p1"):
        await asyncio.sleep(0.01)
    events = [q.get_nowait() for _ in range(q.qsize())]
    done = {e["item"]: e for e in events if e["type"] == "item_done"}
    assert done[1]["ok"] is True
    assert done[2]["ok"] is False
    assert "boom" in done[2]["error"]


# ---------- Finding 3: pid 路径穿越 ----------

async def test_pid_path_traversal_rejected(make_client, tmp_path):
    async with make_client() as client:
        data_dir = tmp_path / "data"
        for bad in ("..%2Fescape", "../escape", "ABCD1234", "deadbeefcafe"):
            r = await client.get(f"/api/projects/{bad}")
            assert r.status_code == 404, bad
            r = await client.put(f"/api/projects/{bad}/artifacts/settings",
                                 json={"content": "x"})
            assert r.status_code == 404, bad
            r = await client.put(f"/api/projects/{bad}/episodes/1/script",
                                 json={"content": "x"})
            assert r.status_code == 404, bad
            r = await client.put(f"/api/projects/{bad}/scripts/1",
                                 json={"content": "x"})
            assert r.status_code == 404, bad
        # data 目录之外不得出现任何逃逸文件
        assert not (tmp_path / "escape").exists()
        assert not (data_dir / "escape").exists()
        assert not (data_dir / "projects" / "escape").exists()


# ---------- Finding 4: 重复 stage1/start 先 409，不得重置状态 ----------

class BlockingGemini:
    def __init__(self):
        self.gate = asyncio.Event()

    async def analyze(self, video_path, prompt):
        await self.gate.wait()
        ep = int(re.search(r"第(\d+)集", prompt).group(1))
        from conftest import GEMINI_OUTPUT_TPL
        return GEMINI_OUTPUT_TPL.format(ep=ep)


async def test_stage1_duplicate_start_409_keeps_statuses(make_client, tmp_path):
    gemini = BlockingGemini()
    async with make_client(gemini=gemini) as client:
        vd = _make_videos(tmp_path, 2)
        pid = await _create_project(client, vd)
        r = await client.post(f"/api/projects/{pid}/stage1/start", json={})
        assert r.status_code == 200
        # 等待批次内 worker 把状态推进到 analyzing
        for _ in range(100):
            r = await client.get(f"/api/projects/{pid}")
            if all(e["status"] == "analyzing" for e in r.json()["episodes"]):
                break
            await asyncio.sleep(0.02)
        else:
            raise TimeoutError
        r = await client.post(f"/api/projects/{pid}/stage1/start", json={})
        assert r.status_code == 409
        r = await client.get(f"/api/projects/{pid}")
        assert all(e["status"] == "analyzing" for e in r.json()["episodes"])
        gemini.gate.set()
        await _wait_not_running(client, pid)
