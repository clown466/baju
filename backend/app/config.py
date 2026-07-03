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
