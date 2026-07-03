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
