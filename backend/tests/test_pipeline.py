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
