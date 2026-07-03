from pathlib import Path
from app.config import load_config

YAML = """
gemini: {api_key: "gk", model: "gemini-2.5-pro"}
text_llm:
  provider: "deepseek"
  providers:
    deepseek: {base_url: "https://api.deepseek.com/v1", api_key: "dk", model: "deepseek-chat"}
"""

def test_load_config(tmp_path: Path):
    p = tmp_path / "config.yaml"
    p.write_text(YAML, encoding="utf-8")
    cfg = load_config(p)
    assert cfg.gemini.api_key == "gk"
    assert cfg.text_llm.providers["deepseek"].model == "deepseek-chat"
    assert cfg.concurrency == 3      # 默认值
    assert cfg.retries == 2
    assert cfg.data_dir == "data"

def test_active_provider(tmp_path: Path):
    p = tmp_path / "config.yaml"
    p.write_text(YAML, encoding="utf-8")
    cfg = load_config(p)
    ap = cfg.text_llm.active()
    assert ap.base_url == "https://api.deepseek.com/v1"
