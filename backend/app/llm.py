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
