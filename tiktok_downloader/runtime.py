"""打包(PyInstaller)与源码两种运行方式的差异都收敛在这里。"""
import os
import subprocess
import sys

IS_FROZEN = getattr(sys, "frozen", False)

# 数据目录：源码运行=脚本目录；打包后=exe 所在目录（便携式）
BASE = (os.path.dirname(os.path.abspath(sys.executable)) if IS_FROZEN
        else os.path.dirname(os.path.abspath(__file__)))

# 无窗口子进程标志（打包成 --noconsole 后避免闪黑框）
NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def ytdlp_cmd() -> str:
    """优先用随软件分发的 yt-dlp.exe，否则用系统 PATH 里的 yt-dlp。"""
    bundled = os.path.join(BASE, "vendor", "yt-dlp.exe")
    if os.path.exists(bundled):
        return bundled
    return "yt-dlp"
