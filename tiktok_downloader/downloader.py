import os
import shutil
import subprocess
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor

from organizer import DownloadTask


def _run_ytdlp(video_id: str, out_path: str, cookies_file: str) -> bool:
    url = f"https://www.tiktok.com/@_/video/{video_id}"
    # 每次调用复制独立 cookies，避免 yt-dlp 并发回写同一文件的竞态
    fd, ck = tempfile.mkstemp(suffix=".txt")
    os.close(fd)
    try:
        shutil.copyfile(cookies_file, ck)
        r = subprocess.run(
            ["yt-dlp", "--cookies", ck, "-q", "--no-progress",
             "--retries", "5",
             "-o", out_path.replace(".mp4", ".%(ext)s"), url],
            capture_output=True, text=True, timeout=300)
        return r.returncode == 0
    except Exception:
        return False
    finally:
        try:
            os.remove(ck)
        except OSError:
            pass


def run_downloads(plan, selected, base_dir, cookies_file, on_progress,
                  stop_event, runner=None, max_workers=3):
    runner = runner or _run_ytdlp
    tasks: list[tuple[DownloadTask, str]] = []
    for series in plan:
        if series not in selected:
            continue
        folder = os.path.join(base_dir, series)
        for t in plan[series]:
            tasks.append((t, os.path.join(folder, t.filename)))

    total = len(tasks)
    done = 0
    failed: list[tuple[DownloadTask, str]] = []
    lock = threading.Lock()

    def work(item):
        nonlocal done
        t, out = item
        if stop_event.is_set():
            return
        os.makedirs(os.path.dirname(out), exist_ok=True)
        ok = True if os.path.exists(out) else runner(t.video_id, out, cookies_file)
        # 锁内只更新状态并取快照，锁外调用回调避免回调耗时串行化所有线程
        with lock:
            done += 1
            if not ok:
                failed.append(item)
            snap_done = done
            snap_failed = len(failed)
        on_progress(snap_done, total, snap_failed,
                    f"{'OK' if ok else 'FAIL'} {t.series}/{t.filename}")

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        list(ex.map(work, tasks))

    # 失败串行重试一轮
    # remaining 从 len(failed) 单调递减到最终 still_failed，保证 UI 失败计数全局语义一致
    remaining_failures = len(failed)
    still_failed = 0
    for t, out in failed:
        if stop_event.is_set():
            still_failed += 1
            continue
        if os.path.exists(out) or runner(t.video_id, out, cookies_file):
            # 重试成功：全局失败数减 1
            remaining_failures -= 1
            on_progress(done, total, remaining_failures, f"重试成功 {t.series}/{t.filename}")
        else:
            still_failed += 1
            # 重试仍失败：全局失败数保持（remaining_failures 不变）
            on_progress(done, total, remaining_failures, f"重试仍失败 {t.series}/{t.filename}")

    if stop_event.is_set():
        return done - len(failed), still_failed
    return total - still_failed, still_failed
