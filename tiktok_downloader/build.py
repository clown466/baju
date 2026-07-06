"""打包脚本：python build.py
产物在 dist/拆剧助手/，把整个文件夹压缩分发即可。
"""
import os
import subprocess
import sys
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
VENDOR = os.path.join(BASE, "vendor")
YTDLP_EXE = os.path.join(VENDOR, "yt-dlp.exe")
YTDLP_URL = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
APP_NAME = "拆剧助手"


def ensure_ytdlp():
    if os.path.exists(YTDLP_EXE):
        print("vendor/yt-dlp.exe 已存在")
        return
    os.makedirs(VENDOR, exist_ok=True)
    print("下载 yt-dlp.exe …")
    urllib.request.urlretrieve(YTDLP_URL, YTDLP_EXE)
    print(f"完成：{os.path.getsize(YTDLP_EXE) // 1024 // 1024} MB")


def build():
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--name", APP_NAME,
        "--noconsole",
        "--onedir",
        # playwright 驱动（node + package）必须完整收集
        "--collect-all", "playwright",
        "app.py",
    ]
    subprocess.run(cmd, cwd=BASE, check=True)
    # 把 yt-dlp.exe 放进产物目录的 vendor/（runtime.ytdlp_cmd 会优先找它）
    dist_vendor = os.path.join(BASE, "dist", APP_NAME, "vendor")
    os.makedirs(dist_vendor, exist_ok=True)
    import shutil
    shutil.copyfile(YTDLP_EXE, os.path.join(dist_vendor, "yt-dlp.exe"))
    print(f"\n打包完成：dist/{APP_NAME}/{APP_NAME}.exe")


if __name__ == "__main__":
    ensure_ytdlp()
    build()
