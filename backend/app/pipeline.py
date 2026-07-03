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
