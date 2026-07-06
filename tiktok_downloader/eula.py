"""首次启动的用户协议与免责声明。用户必须同意才能使用软件。"""
import tkinter as tk
from tkinter import ttk

APP_NAME = "拆剧助手"
EULA_VERSION = 1  # 协议文本有实质修改时 +1，用户需重新同意

EULA_TEXT = f"""\
{APP_NAME} 用户协议与免责声明

请在使用本软件前仔细阅读并同意以下条款。点击"同意并继续"即表示您已阅读、理解并接受全部条款；如不同意，请点击"退出"。

一、软件用途
1. 本软件仅供短剧从业者及爱好者进行个人学习、研究与拆剧参考（如分析剧情结构、
   节奏、镜头语言等）使用。
2. 本软件不提供任何视频内容，仅为用户访问其本人 TikTok 账号可见内容提供
   本地缓存与整理的技术便利。

二、版权与合规
1. 通过本软件下载的全部内容，其著作权归原作者或权利人所有。
2. 用户不得将下载内容用于二次发布、搬运、剪辑再传播、商业用途或其他任何
   侵犯著作权的行为。
3. 用户应遵守所在地法律法规及 TikTok 平台的服务条款。因违反前述规定产生的
   一切法律责任，由用户自行承担。

三、账号与数据
1. 本软件使用用户本人的 TikTok 登录状态进行访问，登录信息仅保存在用户本机，
   不会上传至任何服务器。
2. 因平台风控、验证码、账号异常等导致的功能不可用，本软件不做任何保证。

四、免责声明
1. 本软件按"现状"提供，不对可用性、准确性、持续性做任何明示或默示的保证。
2. 在适用法律允许的最大范围内，开发者不对用户使用本软件所产生的任何直接或
   间接损失（包括但不限于账号受限、数据丢失、法律纠纷）承担责任。
3. 若权利人认为本软件的使用侵犯其合法权益，请通过软件发布渠道联系，
   我们将积极配合处理。

五、其他
1. 开发者可随时更新本协议，更新后首次启动时将再次提示确认。
2. 本协议的解释与适用，以及与之相关的争议，均适用用户所在地法律。
"""


def is_accepted(cfg: dict) -> bool:
    return cfg.get("eula_accepted_version", 0) >= EULA_VERSION


def show_eula(root: tk.Tk) -> bool:
    """模态显示协议，返回用户是否同意。"""
    result = {"ok": False}
    win = tk.Toplevel(root)
    win.title(f"{APP_NAME} - 用户协议与免责声明")
    win.geometry("620x520")
    win.transient(root)
    win.grab_set()
    win.protocol("WM_DELETE_WINDOW", win.destroy)  # 关窗=不同意

    text = tk.Text(win, wrap="word", padx=10, pady=8)
    sb = ttk.Scrollbar(win, command=text.yview)
    text.config(yscrollcommand=sb.set)
    text.insert("1.0", EULA_TEXT)
    text.config(state="disabled")

    btns = ttk.Frame(win, padding=8)
    btns.pack(side="bottom", fill="x")

    def agree():
        result["ok"] = True
        win.destroy()

    ttk.Button(btns, text="同意并继续", command=agree).pack(side="right")
    ttk.Button(btns, text="退出", command=win.destroy).pack(side="right", padx=8)

    sb.pack(side="right", fill="y")
    text.pack(side="left", fill="both", expand=True)

    win.wait_window()
    return result["ok"]
