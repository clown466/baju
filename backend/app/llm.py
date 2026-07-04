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
    """Gemini 原生视频通道。

    upload="files"：Files API 上传（Google 原生密钥）。
    upload="inline"：视频字节内联进 generateContent（适用于不代理
    Files API 的 OpenAI 中转站，受单次请求约 20MB 限制）。
    base_url 可指向中转站的原生 Gemini 路由；None 表示 Google 官方。
    """

    UPLOAD_TIMEOUT = 600  # 等待文件 ACTIVE 的秒数上限
    INLINE_LIMIT = 19 * 1024 * 1024  # 内联上传大小上限（字节）

    MIME_MAP = {
        ".mp4": "video/mp4", ".mkv": "video/x-matroska",
        ".mov": "video/quicktime", ".avi": "video/x-msvideo",
        ".webm": "video/webm", ".ts": "video/mp2t",
        ".flv": "video/x-flv", ".wmv": "video/x-ms-wmv",
        ".3gp": "video/3gpp", ".mpg": "video/mpeg", ".mpeg": "video/mpeg",
    }

    def __init__(self, api_key: str, model: str,
                 base_url: str | None = None, upload: str = "files"):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.upload = upload

    @classmethod
    def _mime_for(cls, filename: str) -> str:
        return cls.MIME_MAP.get(Path(filename).suffix.lower(), "video/mp4")

    def _client(self):
        from google import genai

        if self.base_url:
            return genai.Client(
                api_key=self.api_key,
                http_options={"base_url": self.base_url})
        return genai.Client(api_key=self.api_key)

    def _analyze_inline_sync(self, video_path: Path, prompt: str) -> str:
        size = video_path.stat().st_size
        if size > self.INLINE_LIMIT:
            raise RuntimeError(
                f"视频 {video_path.name}（{size / 1024 / 1024:.1f}MB）超过"
                f"内联上传上限 {self.INLINE_LIMIT / 1024 / 1024:.0f}MB。"
                "请压缩视频，或改用 Google 原生密钥（upload: files）。")
        from google.genai import types

        client = self._client()
        part = types.Part.from_bytes(
            data=video_path.read_bytes(),
            mime_type=self._mime_for(video_path.name))
        resp = client.models.generate_content(
            model=self.model, contents=[part, prompt])
        return resp.text

    def _analyze_sync(self, video_path: Path, prompt: str) -> str:
        if self.upload == "inline":
            return self._analyze_inline_sync(video_path, prompt)
        client = self._client()
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
