import threading
from organizer import DownloadTask
from downloader import run_downloads


def make_plan():
    return {"S": [DownloadTask("v1", "S", "第01集.mp4"),
                  DownloadTask("v2", "S", "第02集.mp4")],
            "T": [DownloadTask("v3", "T", "第01集.mp4")]}


def test_downloads_only_selected_and_reports(tmp_path):
    calls, msgs = [], []
    ok, fail = run_downloads(
        make_plan(), {"S"}, str(tmp_path), "c.txt",
        on_progress=lambda d, t, f, m: msgs.append((d, t, f)),
        stop_event=threading.Event(),
        runner=lambda vid, out, ck: calls.append(vid) or True,
        max_workers=1)
    assert sorted(calls) == ["v1", "v2"] and (ok, fail) == (2, 0)
    assert msgs[-1] == (2, 2, 0)


def test_skips_existing_files(tmp_path):
    (tmp_path / "S").mkdir()
    (tmp_path / "S" / "第01集.mp4").write_bytes(b"x")
    calls = []
    ok, fail = run_downloads(
        make_plan(), {"S"}, str(tmp_path), "c.txt",
        on_progress=lambda *a: None, stop_event=threading.Event(),
        runner=lambda vid, out, ck: calls.append(vid) or True, max_workers=1)
    assert calls == ["v2"] and ok == 2


def test_failed_retried_once(tmp_path):
    attempts = {"v1": 0}
    def flaky(vid, out, ck):
        attempts[vid] += 1
        return attempts[vid] >= 2   # 第一次失败，重试成功
    ok, fail = run_downloads(
        {"S": [DownloadTask("v1", "S", "第01集.mp4")]}, {"S"},
        str(tmp_path), "c.txt", on_progress=lambda *a: None,
        stop_event=threading.Event(), runner=flaky, max_workers=1)
    assert attempts["v1"] == 2 and (ok, fail) == (1, 0)


def test_stop_event_halts(tmp_path):
    ev = threading.Event(); ev.set()
    calls = []
    ok, fail = run_downloads(
        make_plan(), {"S", "T"}, str(tmp_path), "c.txt",
        on_progress=lambda *a: None, stop_event=ev,
        runner=lambda vid, out, ck: calls.append(vid) or True, max_workers=1)
    assert calls == []
