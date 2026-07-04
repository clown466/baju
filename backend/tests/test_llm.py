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


def test_gemini_inline_size_guard(tmp_path):
    """内联模式下超过大小上限直接报错，不调用 SDK。"""
    from pathlib import Path
    from app.llm import GeminiVideo

    video = tmp_path / "ep1.mp4"
    video.write_bytes(b"x" * 1024)
    g = GeminiVideo("sk", "m", upload="inline")
    g.INLINE_LIMIT = 100  # 压低上限便于测试
    with pytest.raises(RuntimeError, match="内联上传"):
        g._analyze_inline_sync(Path(video), "prompt")


def test_gemini_mime_type():
    from app.llm import GeminiVideo
    assert GeminiVideo._mime_for("a.mp4") == "video/mp4"
    assert GeminiVideo._mime_for("b.MKV") == "video/x-matroska"
    assert GeminiVideo._mime_for("c.unknown") == "video/mp4"
