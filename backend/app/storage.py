import json
import re
import uuid
from pathlib import Path

VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".avi", ".ts", ".webm", ".flv"}

_ARTIFACTS = {
    "analysis": ("analysis", "report.md"),
    "settings": ("settings", "new_drama.md"),
    "outline": ("outline", "outline.md"),
}


def _natural_key(name: str):
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", name)]


def scan_videos(video_dir: Path) -> list[Path]:
    files = [f for f in video_dir.iterdir()
             if f.is_file() and f.suffix.lower() in VIDEO_EXTS]
    return sorted(files, key=lambda f: _natural_key(f.name))


class ProjectStore:
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        (self.data_dir / "projects").mkdir(parents=True, exist_ok=True)

    def project_dir(self, pid: str) -> Path:
        return self.data_dir / "projects" / pid

    def _project_json(self, pid: str) -> Path:
        return self.project_dir(pid) / "project.json"

    def create_project(self, name: str, video_dir: str) -> dict:
        pid = uuid.uuid4().hex[:8]
        files = scan_videos(Path(video_dir))
        project = {
            "id": pid,
            "name": name,
            "video_dir": video_dir,
            "episodes": [{"episode": i + 1, "file": f.name}
                         for i, f in enumerate(files)],
        }
        self.save_project(project)
        return project

    def save_project(self, project: dict) -> None:
        self.write(self._project_json(project["id"]),
                   json.dumps(project, ensure_ascii=False, indent=2))

    def get_project(self, pid: str) -> dict:
        return json.loads(self._project_json(pid).read_text(encoding="utf-8"))

    def list_projects(self) -> list[dict]:
        out = []
        for d in sorted((self.data_dir / "projects").iterdir()):
            pj = d / "project.json"
            if pj.exists():
                out.append(json.loads(pj.read_text(encoding="utf-8")))
        return out

    def episode_script_path(self, pid: str, ep: int) -> Path:
        return self.project_dir(pid) / "episodes" / f"ep{ep:03d}.script.md"

    def episode_meta_path(self, pid: str, ep: int) -> Path:
        return self.project_dir(pid) / "episodes" / f"ep{ep:03d}.meta.json"

    def new_script_path(self, pid: str, ep: int) -> Path:
        return self.project_dir(pid) / "scripts" / f"ep{ep:03d}.md"

    def artifact_path(self, pid: str, kind: str) -> Path:
        sub, fname = _ARTIFACTS[kind]
        return self.project_dir(pid) / sub / fname

    def read(self, path: Path) -> str | None:
        return path.read_text(encoding="utf-8") if path.exists() else None

    def write(self, path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
