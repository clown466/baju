import re
from dataclasses import dataclass


@dataclass
class VideoItem:
    id: str
    create_time: int
    desc: str


def clean_series(desc: str) -> str:
    name = re.sub(r"#.*", "", desc or "").strip()
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    name = re.sub(r"\s+", " ", name)
    # 只 strip 开头和结尾的空格与点，但保留下划线
    name = name.strip(" .")
    # 截断到 80 个字符，然后再次 strip 空格和点（但不 strip 下划线）
    name = name[:80].strip(" .") or "未分类"
    return name


def parse_input(text: str) -> tuple[str, str]:
    text = (text or "").strip()
    m = re.match(r"^@([\w.\-]+)$", text)
    if m:
        return ("user", f"https://www.tiktok.com/@{m.group(1)}")
    m = re.match(r"^https?://(?:www\.)?tiktok\.com/(@[\w.\-]+)/video/(\d+)", text)
    if m:
        return ("video", f"https://www.tiktok.com/{m.group(1)}/video/{m.group(2)}")
    m = re.match(r"^https?://(?:www\.)?tiktok\.com/(@[\w.\-]+)/?(?:\?.*)?$", text)
    if m:
        return ("user", f"https://www.tiktok.com/{m.group(1)}")
    raise ValueError(f"无法识别的链接: {text}")
