import json
import re
import subprocess
import time

from cookies_io import write_netscape
from organizer import VideoItem


class NeedLoginError(Exception):
    pass


class ChromeNotFoundError(Exception):
    pass


def _collect_single(url: str) -> list[VideoItem]:
    r = subprocess.run(
        ["yt-dlp", "--no-download", "--print", "%(id)s\t%(timestamp)s\t%(title)s", url],
        capture_output=True, text=True, timeout=120, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"获取视频信息失败: {r.stderr[-200:]}")
    vid, ts, title = r.stdout.strip().split("\t", 2)
    ts = int(ts) if ts.isdigit() else 0
    return [VideoItem(vid, ts, title)]


def collect(url, kind, profile_dir, cookies_out, on_status, chrome_path=None):
    if kind == "video":
        on_status("获取单视频信息…")
        return _collect_single(url)

    from playwright.sync_api import sync_playwright

    seen: dict[str, VideoItem] = {}
    state = {"has_more": True, "batches": 0}

    with sync_playwright() as p:
        kwargs = dict(user_data_dir=profile_dir, headless=False,
                      args=["--lang=en-US"])
        if chrome_path:
            kwargs["executable_path"] = chrome_path
        else:
            kwargs["channel"] = "chrome"
        try:
            ctx = p.chromium.launch_persistent_context(**kwargs)
        except Exception as e:
            raise ChromeNotFoundError(str(e)) from e

        page = ctx.new_page()

        def on_response(res):
            if "api/post/item_list" not in res.url:
                return
            try:
                data = res.json()
            except Exception:
                return
            for it in data.get("itemList") or []:
                seen[it["id"]] = VideoItem(
                    it["id"], int(it.get("createTime") or 0),
                    re.sub(r"[\t\n]", " ", it.get("desc") or ""))
            state["has_more"] = bool(data.get("hasMore"))
            state["batches"] += 1
            on_status(f"已采集 {len(seen)} 个视频…")

        page.on("response", on_response)
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(6000)

        stall, last = 0, 0
        for i in range(500):
            if not state["has_more"] and state["batches"] > 0:
                break
            if seen:
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(1500)
                if len(seen) == last:
                    stall += 1
                    if stall >= 20:
                        break
                else:
                    stall, last = 0, len(seen)
            else:
                # 尚无数据：可能是滑块验证/登录墙。不滚动以免干扰用户操作，
                # 定期刷新页面以在验证完成后重新触发数据请求
                page.wait_for_timeout(1500)
                if i == 5:
                    on_status("如浏览器出现滑块验证或登录提示，请手动完成后等待…")
                if i == 20 and page.locator(
                        "#loginContainer, [data-e2e='login-modal']").count():
                    ctx.close()
                    raise NeedLoginError("需要登录")
                if i > 0 and i % 30 == 0:
                    page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    page.wait_for_timeout(4000)
                if i >= 150:  # 约 4 分钟仍无数据 → 放弃
                    break

        # DOM 兜底补充
        for a in page.eval_on_selector_all(
                "a[href*='/video/']", "els => els.map(a => a.href)"):
            m = re.search(r"video/(\d+)", a)
            if m and m.group(1) not in seen:
                seen[m.group(1)] = VideoItem(m.group(1), 0, "")

        write_netscape(ctx.cookies(), cookies_out)
        ctx.close()

    if not seen:
        raise NeedLoginError("未采集到任何视频，可能需要登录")
    on_status(f"采集完成，共 {len(seen)} 个视频")
    return list(seen.values())
