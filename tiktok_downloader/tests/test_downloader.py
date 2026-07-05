import os
import threading
from unittest.mock import patch, MagicMock
from organizer import DownloadTask
from downloader import run_downloads, _run_ytdlp


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


def test_stop_event_mid_way_halts_subsequent(tmp_path):
    """stop_event 在处理第一个任务后置位时，后续任务的 runner 不再被调用。"""
    ev = threading.Event()
    calls = []

    def runner_that_stops(vid, out, ck):
        calls.append(vid)
        # 第一个任务处理完成后置位 stop_event
        ev.set()
        return True

    # 使用单线程 max_workers=1 保证串行执行，确保第一个任务触发 stop 后其余任务不执行
    plan = {"S": [DownloadTask("v1", "S", "第01集.mp4"),
                  DownloadTask("v2", "S", "第02集.mp4"),
                  DownloadTask("v3", "S", "第03集.mp4")]}
    run_downloads(
        plan, {"S"}, str(tmp_path), "c.txt",
        on_progress=lambda *a: None, stop_event=ev,
        runner=runner_that_stops, max_workers=1)

    # 只有第一个任务的 runner 被调用，后续任务因 stop_event 被跳过
    assert calls == ["v1"], f"期望只调用 v1，实际调用了 {calls}"


# ── 新增测试：覆盖三个修复点 ──────────────────────────────────────────────────

def test_missing_cookies_file_runs_without_cookies(tmp_path):
    """Finding 1: cookies 文件不存在时，_run_ytdlp 应不带 --cookies 调用 yt-dlp，而非静默返回 False。"""
    fake_result = MagicMock()
    fake_result.returncode = 0
    fake_result.stderr = ""

    captured_cmds = []

    def fake_run(cmd, **kwargs):
        captured_cmds.append(cmd)
        return fake_result

    out_path = str(tmp_path / "video.mp4")
    with patch("downloader.subprocess.run", side_effect=fake_run):
        ok, err = _run_ytdlp("vid123", out_path, "/nonexistent/cookies.txt")

    assert ok is True
    assert len(captured_cmds) == 1
    # --cookies 不应出现在命令中
    assert "--cookies" not in captured_cmds[0], "不存在的 cookies 文件不应导致 --cookies 参数被传入"


def test_failed_txt_written_for_still_failed_items(tmp_path):
    """Finding 2: 重试后仍失败的条目应写入 <base_dir>/failed.txt。"""
    def always_fail(vid, out, ck):
        return False  # 返回 bool，兼容旧注入接口

    ok, fail = run_downloads(
        {"S": [DownloadTask("v1", "S", "第01集.mp4"),
               DownloadTask("v2", "S", "第02集.mp4")]},
        {"S"}, str(tmp_path), "c.txt",
        on_progress=lambda *a: None,
        stop_event=threading.Event(),
        runner=always_fail, max_workers=1)

    assert fail == 2
    failed_txt = tmp_path / "failed.txt"
    assert failed_txt.exists(), "failed.txt 应被创建"
    content = failed_txt.read_text(encoding="utf-8")
    assert "v1" in content
    assert "v2" in content
    assert "S/第01集.mp4" in content
    assert "S/第02集.mp4" in content


def test_failure_message_includes_stderr_tail(tmp_path):
    """Finding 3: 失败时 on_progress 收到的消息应包含 stderr 尾部信息。"""
    stderr_output = "ERROR: some long error from yt-dlp about network timeout"

    def failing_runner_with_stderr(vid, out, ck):
        # 新接口：返回 (bool, stderr_tail)
        return (False, stderr_output[-200:])

    msgs = []
    run_downloads(
        {"S": [DownloadTask("v1", "S", "第01集.mp4")]}, {"S"},
        str(tmp_path), "c.txt",
        on_progress=lambda d, t, f, m: msgs.append(m),
        stop_event=threading.Event(),
        runner=failing_runner_with_stderr, max_workers=1)

    # 找到包含 FAIL 的消息（初次或重试）
    fail_msgs = [m for m in msgs if "FAIL" in m or "重试仍失败" in m]
    assert fail_msgs, "应有失败消息"
    # 至少有一条消息包含 stderr 尾部
    assert any(stderr_output[-200:] in m for m in fail_msgs), \
        f"失败消息应包含 stderr 尾部，实际消息: {fail_msgs}"
