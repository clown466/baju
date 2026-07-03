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
