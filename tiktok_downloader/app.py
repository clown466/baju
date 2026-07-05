import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import config
from collector import ChromeNotFoundError, NeedLoginError, collect
from downloader import run_downloads
from organizer import parse_input, plan_downloads

BASE = os.path.dirname(os.path.abspath(__file__))
PROFILE_DIR = os.path.join(BASE, "chrome_profile")
COOKIES = os.path.join(BASE, "cookies.txt")


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("TikTok 剧集下载器")
        root.geometry("640x560")
        self.q = queue.Queue()
        self.plan = {}
        self.stop_event = threading.Event()
        cfg = config.load()

        top = ttk.Frame(root, padding=8); top.pack(fill="x")
        ttk.Label(top, text="账号/视频链接:").grid(row=0, column=0, sticky="w")
        self.url_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.url_var, width=52).grid(row=0, column=1, padx=4)
        self.btn_collect = ttk.Button(top, text="采集", command=self.on_collect)
        self.btn_collect.grid(row=0, column=2)

        ttk.Label(top, text="下载目录:").grid(row=1, column=0, sticky="w", pady=4)
        self.dir_var = tk.StringVar(value=cfg.get("last_dir", os.path.join(BASE, "下载")))
        ttk.Entry(top, textvariable=self.dir_var, width=52).grid(row=1, column=1, padx=4)
        ttk.Button(top, text="浏览...", command=self.on_browse).grid(row=1, column=2)

        mid = ttk.Frame(root, padding=(8, 0)); mid.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(mid, columns=("eps",), selectmode="none", height=12)
        self.tree.heading("#0", text="剧名（点击勾选/取消）")
        self.tree.heading("eps", text="集数")
        self.tree.column("eps", width=60, anchor="center")
        self.tree.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(mid, command=self.tree.yview); sb.pack(side="right", fill="y")
        self.tree.config(yscrollcommand=sb.set)
        self.tree.bind("<Button-1>", self.on_tree_click)
        self.checked: dict[str, bool] = {}

        btns = ttk.Frame(root, padding=8); btns.pack(fill="x")
        ttk.Button(btns, text="全选", command=lambda: self.set_all(True)).pack(side="left")
        ttk.Button(btns, text="全不选", command=lambda: self.set_all(False)).pack(side="left", padx=4)
        self.btn_dl = ttk.Button(btns, text="开始下载", command=self.on_download, state="disabled")
        self.btn_dl.pack(side="left", padx=12)
        self.btn_stop = ttk.Button(btns, text="停止", command=self.on_stop, state="disabled")
        self.btn_stop.pack(side="left")

        self.prog = ttk.Progressbar(root, maximum=100); self.prog.pack(fill="x", padx=8)
        self.status = tk.StringVar(value="就绪")
        ttk.Label(root, textvariable=self.status).pack(anchor="w", padx=8)
        self.log = tk.Text(root, height=8, state="disabled")
        self.log.pack(fill="both", expand=False, padx=8, pady=(4, 8))
        root.after(100, self.poll)

    # ---------- 界面事件 ----------
    def on_browse(self):
        d = filedialog.askdirectory()
        if d:
            self.dir_var.set(d)

    def on_tree_click(self, ev):
        iid = self.tree.identify_row(ev.y)
        if iid:
            self.checked[iid] = not self.checked.get(iid, True)
            self.render_row(iid)

    def set_all(self, val: bool):
        for iid in self.checked:
            self.checked[iid] = val
            self.render_row(iid)

    def render_row(self, series: str):
        mark = "☑" if self.checked[series] else "☐"
        self.tree.item(series, text=f"{mark} {series}")

    def logline(self, msg: str):
        self.log.config(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.log.config(state="disabled")

    # ---------- 采集 ----------
    def on_collect(self):
        try:
            kind, url = parse_input(self.url_var.get())
        except ValueError as e:
            messagebox.showerror("链接错误", str(e))
            return
        self.btn_collect.config(state="disabled")
        self.status.set("采集中…（首次使用请在打开的浏览器里登录 TikTok）")
        threading.Thread(target=self.collect_worker, args=(url, kind), daemon=True).start()

    def collect_worker(self, url: str, kind: str):
        cfg = config.load()
        try:
            items = collect(url, kind, PROFILE_DIR, COOKIES,
                            on_status=lambda m: self.q.put(("status", m)),
                            chrome_path=cfg.get("chrome_path"))
            self.q.put(("collected", items))
        except NeedLoginError:
            self.q.put(("need_login", url, kind))
        except ChromeNotFoundError as e:
            self.q.put(("no_chrome", str(e)))
        except Exception as e:
            self.q.put(("error", f"采集失败: {e}"))

    # ---------- 下载 ----------
    def on_download(self):
        selected = {s for s, v in self.checked.items() if v}
        if not selected:
            messagebox.showinfo("提示", "请先勾选要下载的剧")
            return
        base = self.dir_var.get().strip()
        os.makedirs(base, exist_ok=True)
        cfg = config.load(); cfg["last_dir"] = base; config.save(cfg)
        self.stop_event.clear()
        self.btn_dl.config(state="disabled"); self.btn_stop.config(state="normal")
        threading.Thread(target=self.download_worker,
                         args=(selected, base), daemon=True).start()

    def download_worker(self, selected: set, base: str):
        try:
            ok, fail = run_downloads(
                self.plan, selected, base, COOKIES,
                on_progress=lambda d, t, f, m: self.q.put(("prog", d, t, f, m)),
                stop_event=self.stop_event)
            self.q.put(("done", ok, fail))
        except Exception as e:
            self.q.put(("error", f"下载失败: {e}"))

    def on_stop(self):
        self.stop_event.set()
        self.status.set("正在停止…（等待在途任务完成）")

    # ---------- 队列轮询 ----------
    def poll(self):
        try:
            while True:
                msg = self.q.get_nowait()
                self.handle(msg)
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    def handle(self, msg):
        kind = msg[0]
        if kind == "status":
            self.status.set(msg[1])
        elif kind == "collected":
            self.plan = plan_downloads(msg[1])
            self.tree.delete(*self.tree.get_children())
            self.checked.clear()
            for series in sorted(self.plan, key=lambda s: -len(self.plan[s])):
                self.tree.insert("", "end", iid=series, values=(len(self.plan[series]),))
                self.checked[series] = True
                self.render_row(series)
            total = sum(len(v) for v in self.plan.values())
            self.status.set(f"采集完成：{len(self.plan)} 部剧 / {total} 集")
            self.btn_collect.config(state="normal")
            self.btn_dl.config(state="normal")
        elif kind == "prog":
            _, d, t, f, m = msg
            self.prog.config(maximum=max(t, 1), value=d)
            self.status.set(f"下载中 {d}/{t}  失败:{f}")
            self.logline(m)
        elif kind == "done":
            _, ok, fail = msg
            self.status.set(f"完成：成功 {ok}，失败 {fail}")
            self.btn_dl.config(state="normal"); self.btn_stop.config(state="disabled")
            messagebox.showinfo("完成", f"下载结束\n成功 {ok} 集，失败 {fail} 集")
        elif kind == "need_login":
            self.btn_collect.config(state="normal")
            self.status.set("需要登录")
            if messagebox.askretrycancel(
                    "需要登录", "请在弹出的浏览器里登录 TikTok，然后点[重试]"):
                self.url_var.set(self.url_var.get())
                self.on_collect()
        elif kind == "no_chrome":
            self.btn_collect.config(state="normal")
            self.status.set("未找到 Chrome")
            if messagebox.askokcancel("未找到 Chrome", "请选择 chrome.exe 的位置"):
                p = filedialog.askopenfilename(
                    title="选择 chrome.exe", filetypes=[("Chrome", "chrome.exe")])
                if p:
                    cfg = config.load(); cfg["chrome_path"] = p; config.save(cfg)
                    self.on_collect()
        elif kind == "error":
            self.btn_collect.config(state="normal")
            self.btn_dl.config(state="normal" if self.plan else "disabled")
            self.btn_stop.config(state="disabled")
            self.status.set(msg[1])
            messagebox.showerror("错误", msg[1])


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
