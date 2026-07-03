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
