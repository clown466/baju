import os
import sys
import threading
import webbrowser
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import router
from app.config import (AppConfig, GeminiConfig, ProviderConfig,
                        TextLLMConfig, load_config, save_config)
from app.db import StatusDB
from app.engine import BatchRunner, EventBus
from app.llm import GeminiVideo, make_text_llm
from app.storage import ProjectStore


def create_app(cfg: AppConfig, gemini=None, text_llm=None,
               config_path: str | Path = "config.yaml",
               static_dir: str | Path | None = None) -> FastAPI:
    app = FastAPI(title="短剧扒剧与仿写")
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"],
        allow_methods=["*"], allow_headers=["*"])
    data_dir = Path(cfg.data_dir)
    app.state.cfg = cfg
    app.state.config_path = Path(config_path)
    app.state.store = ProjectStore(data_dir)
    app.state.db = StatusDB(data_dir / "status.db")
    app.state.bus = EventBus()
    app.state.runner = BatchRunner(cfg.concurrency, app.state.bus)
    app.state.gemini = gemini or GeminiVideo(
        cfg.gemini.api_key, cfg.gemini.model,
        base_url=cfg.gemini.base_url, upload=cfg.gemini.upload)
    app.state.text_llm = text_llm or make_text_llm(cfg)
    app.include_router(router)
    if static_dir and Path(static_dir).is_dir():
        app.mount("/", StaticFiles(directory=static_dir, html=True))
    return app


def _default_config() -> AppConfig:
    return AppConfig(
        gemini=GeminiConfig(api_key=""),
        text_llm=TextLLMConfig(provider="default", providers={
            "default": ProviderConfig(
                base_url="https://api.openai.com/v1", api_key="", model="")}))


def _find_static() -> Path | None:
    if getattr(sys, "frozen", False):  # PyInstaller 打包运行
        return Path(sys._MEIPASS) / "static"
    dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    return dist if dist.is_dir() else None


def run() -> None:
    import uvicorn
    if getattr(sys, "frozen", False):
        # 打包模式：config.yaml 与 data 目录放在 exe 同级目录
        os.chdir(Path(sys.executable).parent)
    if not Path("config.yaml").exists():
        save_config(_default_config())
    app = create_app(load_config(), static_dir=_find_static())
    url = "http://127.0.0.1:8000"
    if getattr(sys, "frozen", False):
        threading.Timer(1.0, webbrowser.open, [url]).start()
        print(f"服务已启动：{url}（浏览器将自动打开，请勿关闭本窗口）")
    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    run()
