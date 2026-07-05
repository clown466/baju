from pathlib import Path

import yaml
from pydantic import BaseModel


class ProviderConfig(BaseModel):
    base_url: str
    api_key: str
    model: str


class GeminiConfig(BaseModel):
    api_key: str
    model: str = "gemini-2.5-pro"
    base_url: str | None = None  # 中转站原生通道地址；None 表示 Google 官方
    upload: str = "files"  # files=Files API（原生密钥）；inline=内联 base64（中转站）


class TextLLMConfig(BaseModel):
    provider: str
    providers: dict[str, ProviderConfig]

    def active(self) -> ProviderConfig:
        return self.providers[self.provider]


class AppConfig(BaseModel):
    gemini: GeminiConfig
    text_llm: TextLLMConfig
    concurrency: int = 3
    retries: int = 2
    data_dir: str = "data"


def load_config(path: str | Path = "config.yaml") -> AppConfig:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return AppConfig.model_validate(data)


def save_config(cfg: AppConfig, path: str | Path = "config.yaml") -> None:
    Path(path).write_text(
        yaml.safe_dump(cfg.model_dump(), allow_unicode=True, sort_keys=False),
        encoding="utf-8")
