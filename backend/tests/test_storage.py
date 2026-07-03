from pathlib import Path
from app.storage import ProjectStore, scan_videos

def make_videos(d: Path, names: list[str]):
    d.mkdir(parents=True, exist_ok=True)
    for n in names:
        (d / n).write_bytes(b"\x00")

def test_scan_natural_order(tmp_path: Path):
    vd = tmp_path / "videos"
    make_videos(vd, ["第10集.mp4", "第2集.mp4", "第1集.mp4", "notes.txt"])
    files = scan_videos(vd)
    assert [f.name for f in files] == ["第1集.mp4", "第2集.mp4", "第10集.mp4"]

def test_create_and_get_project(tmp_path: Path):
    vd = tmp_path / "videos"
    make_videos(vd, ["ep1.mp4", "ep2.mp4"])
    store = ProjectStore(tmp_path / "data")
    p = store.create_project("测试剧", str(vd))
    assert p["name"] == "测试剧"
    assert p["episodes"] == [
        {"episode": 1, "file": "ep1.mp4"},
        {"episode": 2, "file": "ep2.mp4"},
    ]
    assert store.get_project(p["id"])["name"] == "测试剧"
    assert [x["id"] for x in store.list_projects()] == [p["id"]]

def test_paths_and_io(tmp_path: Path):
    store = ProjectStore(tmp_path / "data")
    vd = tmp_path / "v"; make_videos(vd, ["a.mp4"])
    p = store.create_project("x", str(vd))
    sp = store.episode_script_path(p["id"], 3)
    assert sp.name == "ep003.script.md"
    assert store.read(sp) is None
    store.write(sp, "内容")
    assert store.read(sp) == "内容"
    assert store.artifact_path(p["id"], "analysis").name == "report.md"
    assert store.new_script_path(p["id"], 12).name == "ep012.md"
