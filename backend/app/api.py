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
