import os
import shutil
import subprocess
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor

from organizer import DownloadTask
from runtime import NO_WINDOW, ytdlp_cmd


def _run_ytdlp(video_id: str, out_path: str, cookies_file: str) -> tuple[bool, str]:
    """返回 (成功与否, 错误尾信息)；错误尾信息最多 200 字符。"""
    url = f"https://www.tiktok.com/@_/video/{video_id}"
    cmd = [ytdlp_cmd(), "-q", "--no-progress", "--retries", "5",
           "-o", out_path.replace(".mp4", ".%(ext)s"), url]

    # 若 cookies 文件存在则复制临时副本（避免并发回写竞态），否则不带 --cookies 运行
    ck = None
    if cookies_file and os.path.exists(cookies_file):
        fd, ck = tempfile.mkstemp(suffix=".txt")
        os.close(fd)
        try:
            shutil.copyfile(cookies_file, ck)
        except OSError:
            ck = None
    if ck:
        cmd = [ytdlp_cmd(), "--cookies", ck, "-q", "--no-progress",
               "--retries", "5",
               "-o", out_path.replace(".mp4", ".%(ext)s"), url]

    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300,
                           creationflags=NO_WINDOW)
        if r.returncode == 0:
            return True, ""
        tail = r.stderr[-200:] if r.stderr else ""
        return False, tail
    except Exception as e:
        return False, str(e)[-200:]
    finally:
        if ck:
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

    def _call_runner(vid, out, ck):
        """统一 runner 调用：兼容返回 bool 的旧注入器和返回 (bool, str) 的新接口。"""
        result = runner(vid, out, ck)
        if isinstance(result, tuple):
            return result
        return (bool(result), "")

    def work(item):
        nonlocal done
        t, out = item
        if stop_event.is_set():
            return
        os.makedirs(os.path.dirname(out), exist_ok=True)
        if os.path.exists(out):
            ok, err_tail = True, ""
        else:
            ok, err_tail = _call_runner(t.video_id, out, cookies_file)
        # 锁内只更新状态并取快照，锁外调用回调避免回调耗时串行化所有线程
        with lock:
            done += 1
            if not ok:
                failed.append(item)
            snap_done = done
            snap_failed = len(failed)
        msg = f"{'OK' if ok else 'FAIL'} {t.series}/{t.filename}"
        if not ok and err_tail:
            msg += f" | {err_tail}"
        on_progress(snap_done, total, snap_failed, msg)

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        list(ex.map(work, tasks))

    # 失败串行重试一轮
    # remaining 从 len(failed) 单调递减到最终 still_failed，保证 UI 失败计数全局语义一致
    remaining_failures = len(failed)
    still_failed_items: list[tuple[DownloadTask, str]] = []
    for t, out in failed:
        if stop_event.is_set():
            still_failed_items.append((t, out))
            continue
        if os.path.exists(out):
            remaining_failures -= 1
            on_progress(done, total, remaining_failures, f"重试成功 {t.series}/{t.filename}")
        else:
            retry_ok, err_tail = _call_runner(t.video_id, out, cookies_file)
            if retry_ok:
                # 重试成功：全局失败数减 1
                remaining_failures -= 1
                on_progress(done, total, remaining_failures, f"重试成功 {t.series}/{t.filename}")
            else:
                still_failed_items.append((t, out))
                # 重试仍失败：全局失败数保持（remaining_failures 不变）
                msg = f"重试仍失败 {t.series}/{t.filename}"
                if err_tail:
                    msg += f" | {err_tail}"
                on_progress(done, total, remaining_failures, msg)

    still_failed = len(still_failed_items)

    # 将最终仍失败的条目写入 failed.txt
    if still_failed_items:
        failed_txt = os.path.join(base_dir, "failed.txt")
        with open(failed_txt, "w", encoding="utf-8") as fh:
            for t, out in still_failed_items:
                fh.write(f"{t.video_id}\t{t.series}/{t.filename}\n")

    if stop_event.is_set():
        return done - len(failed), still_failed
    return total - still_failed, still_failed
