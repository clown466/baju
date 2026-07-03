from datetime import date


def export_full(title: str, scripts: dict[int, str | None]) -> str:
    eps = sorted(scripts)
    ok = sum(1 for e in eps if scripts[e])
    parts = [
        f"《{title}》全剧剧本汇总", "",
        "基本信息", "",
        f"- 总集数:{len(eps)}",
        f"- 成功:{ok} 集 / 失败:{len(eps) - ok} 集",
        f"- 生成时间:{date.today().isoformat()}", "",
        "目录", "",
    ]
    parts += [f"- [第{e}集](#第{e}集)" for e in eps]
    for e in eps:
        parts += ["", f"第{e}集", "", scripts[e] or "（本集缺失）"]
    return "\n".join(parts)
