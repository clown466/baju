import re
from dataclasses import dataclass, field

# 场次头：`1-4  夜  内  博物馆柜台`
SCENE_RE = re.compile(r"^(\d+)-(\d+)\s+(\S+)\s+(内外|内|外)\s+(\S.*)$")


@dataclass
class Scene:
    episode: int
    number: int
    time: str
    place_type: str
    location: str
    lines: list[str] = field(default_factory=list)


@dataclass
class EpisodeScript:
    episode: int
    scenes: list[Scene]


def parse_script(text: str) -> EpisodeScript:
    scenes: list[Scene] = []
    for raw in text.splitlines():
        line = raw.rstrip()
        m = SCENE_RE.match(line.strip())
        if m:
            scenes.append(Scene(
                episode=int(m.group(1)), number=int(m.group(2)),
                time=m.group(3), place_type=m.group(4),
                location=m.group(5).strip(),
            ))
        elif scenes and line.strip():
            scenes[-1].lines.append(line.strip())
    episode = scenes[0].episode if scenes else 0
    return EpisodeScript(episode=episode, scenes=scenes)


def validate_script(text: str, expected_episode: int) -> list[str]:
    errors: list[str] = []
    script = parse_script(text)
    if not script.scenes:
        errors.append("未找到任何场次头")
        return errors
    for sc in script.scenes:
        if sc.episode != expected_episode:
            errors.append(f"场 {sc.episode}-{sc.number} 集数与期望({expected_episode})不符")
    numbers = [sc.number for sc in script.scenes]
    for i, n in enumerate(numbers, start=1):
        if n != i:
            errors.append(f"场号不连续：第 {i} 个场次的场号是 {n}")
            break
    return errors
