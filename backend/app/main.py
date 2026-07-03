from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router
from app.config import AppConfig, load_config
from app.db import StatusDB
from app.engine import BatchRunner, EventBus
from app.llm import GeminiVideo, make_text_llm
from app.storage import ProjectStore


def create_app(cfg: AppConfig, gemini=None, text_llm=None) -> FastAPI:
    app = FastAPI(title="短剧扒剧与仿写")
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"],
        allow_methods=["*"], allow_headers=["*"])
    data_dir = Path(cfg.data_dir)
    app.state.cfg = cfg
    app.state.store = ProjectStore(data_dir)
    app.state.db = StatusDB(data_dir / "status.db")
    app.state.bus = EventBus()
    app.state.runner = BatchRunner(cfg.concurrency, app.state.bus)
    app.state.gemini = gemini or GeminiVideo(cfg.gemini.api_key, cfg.gemini.model)
    app.state.text_llm = text_llm or make_text_llm(cfg)
    app.include_router(router)
    return app


def run() -> None:
    import uvicorn
    uvicorn.run(create_app(load_config()), host="127.0.0.1", port=8000)


if __name__ == "__main__":
    run()
