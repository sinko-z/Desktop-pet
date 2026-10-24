"""设置窗口：自启动、置顶、走动、休息提醒、心情问候、大模型接口。"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import messagebox

from . import autostart, config, dialogue, ui


class SettingsWindow:
    def __init__(self, app):
        self.app = app
        self.root: tk.Tk = app.root
        cfg = app.config
        self._queue: queue.Queue = queue.Queue()

        self.autostart_var = tk.BooleanVar(value=cfg["autostart"])
        self.topmost_var = tk.BooleanVar(value=cfg["always_on_top"])
        self.wander_var = tk.BooleanVar(value=cfg["wander"])
        self.remind_var = tk.BooleanVar(value=cfg["remind_rest"])
        self.rest_min_var = tk.IntVar(value=cfg["rest_interval_min"])
        self.snooze_var = tk.IntVar(value=cfg["rest_snooze_min"])
        self.mood_var = tk.IntVar(value=cfg["mood_check_min"])
        self.height_var = tk.IntVar(value=cfg["pet_height"])
        self.name_var = tk.StringVar(value=cfg["user_name"])
        self.llm_enabled_var = tk.BooleanVar(value=cfg["llm"]["enabled"])
        self.base_var = tk.StringVar(value=cfg["llm"]["base_url"])
        self.key_var = tk.StringVar(value=cfg["llm"]["api_key"])
        self.model_var = tk.StringVar(value=cfg["llm"]["model"])

        self.win = tk.Toplevel(self.root)
        self.win.title("Desktop Pet 设置")
        self.win.configure(bg=ui.BG)
        ui.center_window(self.win, 620, 720)
        self.win.minsize(560, 560)
        self.win.protocol("WM_DELETE_WINDOW", self.close)

        self._build()

    # ---------- 界面 ----------
    def _build(self) -> None:
        scroll = ui.ScrollFrame(self.win)
        scroll.pack(fill="both", expand=True, padx=20, pady=(18, 0))
        body = scroll.inner

        basic = self._section(body, "基本")
        self._check(basic, "开机自动启动", self.autostart_var)
        self._check(basic, "宠物窗口始终置顶", self.topmost_var)
        self._check(basic, "允许宠物自己走动", self.wander_var)
        self._spin(basic, "宠物高度（像素）", self.height_var, 100, 320)
        self._entry(basic, "怎么称呼你", self.name_var)

        rest = self._section(body, "久坐与心情提醒")
        self._check(rest, "连续使用电脑后提醒我休息", self.remind_var)
        self._spin(rest, "提醒间隔（分钟）", self.rest_min_var, 10, 240)
        self._spin(rest, "提醒后延后（分钟）", self.snooze_var, 5, 60)
        self._spin(rest, "心情问候间隔（分钟）", self.mood_var, 30, 480)
        ui.label(rest, "键鼠静止超过 5 分钟会暂停计时，不会误打扰。", 8,
                 fg=ui.MUTED, bg=ui.CARD).pack(anchor="w", pady=(6, 0))

        llm = self._section(body, "陪伴对话（可选接入大模型）")
        self._check(llm, "启用大模型对话", self.llm_enabled_var)
        self._entry(llm, "接口地址", self.base_var,
                    hint="OpenAI 兼容接口，例如 https://api.deepseek.com/v1")
        self._entry(llm, "API Key", self.key_var, secret=True)
        self._entry(llm, "模型名称", self.model_var, hint="例如 deepseek-chat")

        test_row = tk.Frame(llm, bg=ui.CARD)
        test_row.pack(fill="x", pady=(8, 0))
        ui.ghost(test_row, "测试连接", self._test).pack(side="left")
        self.test_label = ui.label(test_row, "", 9, fg=ui.MUTED, bg=ui.CARD)
        self.test_label.pack(side="left", padx=(10, 0))
        ui.label(llm, "不填也能正常使用，此时由本地话术陪伴；Key 只保存在本机 data/config.json。",
                 8, fg=ui.MUTED, bg=ui.CARD, wraplength=500, justify="left").pack(anchor="w", pady=(6, 0))

        footer = tk.Frame(self.win, bg=ui.BG)
        footer.pack(fill="x", padx=20, pady=14)
        ui.primary(footer, "保存", self._save).pack(side="right")
        ui.ghost(footer, "取消", self.close).pack(side="right", padx=(0, 10))

    def _section(self, parent, title: str) -> tk.Frame:
        ui.label(parent, title, 12, True).pack(anchor="w", pady=(14, 6))
        card = tk.Frame(parent, bg=ui.CARD, padx=16, pady=12)
        card.pack(fill="x")
        return card

    def _check(self, parent, text: str, var) -> None:
        tk.Checkbutton(parent, text=text, variable=var, bg=ui.CARD, activebackground=ui.CARD,
                       font=ui.font(10), anchor="w", selectcolor=ui.CARD,
                       highlightthickness=0, bd=0).pack(fill="x", pady=2)

    def _spin(self, parent, text: str, var, low: int, high: int) -> None:
        row = tk.Frame(parent, bg=ui.CARD)
        row.pack(fill="x", pady=3)
        ui.label(row, text, 10, bg=ui.CARD).pack(side="left")
        tk.Spinbox(row, from_=low, to=high, textvariable=var, width=8, font=ui.font(10),
                   relief="flat", bg=ui.BG, justify="center",
                   highlightthickness=1, highlightbackground=ui.LINE).pack(side="right")

    def _entry(self, parent, text: str, var, secret: bool = False, hint: str = "") -> None:
        ui.label(parent, text, 9, fg=ui.MUTED, bg=ui.CARD).pack(anchor="w", pady=(8, 3))
        tk.Entry(parent, textvariable=var, font=ui.font(10), bg=ui.BG, fg=ui.INK,
                 relief="flat", highlightthickness=1, highlightbackground=ui.LINE,
                 highlightcolor=ui.ACCENT, show="*" if secret else "").pack(
            fill="x", ipady=6)
        if hint:
            ui.label(parent, hint, 8, fg=ui.MUTED, bg=ui.CARD).pack(anchor="w", pady=(2, 0))

    # ---------- 行为 ----------
    def _collect_llm(self) -> dict:
        return {
            "enabled": bool(self.llm_enabled_var.get()),
            "base_url": self.base_var.get().strip(),
            "api_key": self.key_var.get().strip(),
            "model": self.model_var.get().strip(),
        }

    def _test(self) -> None:
        llm = self._collect_llm()
        if not (llm["base_url"] and llm["api_key"] and llm["model"]):
            self.test_label.configure(text="请先填写接口地址、Key 和模型", fg="#B4553F")
            return
        self.test_label.configure(text="正在连接…", fg=ui.MUTED)
        threading.Thread(target=self._test_worker, args=(llm,), daemon=True).start()
        self.win.after(150, self._test_poll)

    def _test_worker(self, llm: dict) -> None:
        try:
            text = dialogue.llm_reply(
                [{"role": "me", "text": "你好"}], "测试宠物",
                self.app.config["user_name"], llm,
            )
            self._queue.put((True, text))
        except Exception as exc:  # noqa: BLE001
            self._queue.put((False, str(exc)))

    def _test_poll(self) -> None:
        if not self.win.winfo_exists():
            return
        try:
            ok, message = self._queue.get_nowait()
        except queue.Empty:
            self.win.after(200, self._test_poll)
            return
        if ok:
            preview = message.replace("\n", " ")[:40]
            self.test_label.configure(text=f"连接成功：{preview}", fg="#4C7A4E")
        else:
            self.test_label.configure(text=f"失败：{message[:60]}", fg="#B4553F")

    def _save(self) -> None:
        cfg = self.app.config
        cfg["autostart"] = bool(self.autostart_var.get())
        cfg["always_on_top"] = bool(self.topmost_var.get())
        cfg["wander"] = bool(self.wander_var.get())
        cfg["remind_rest"] = bool(self.remind_var.get())
        cfg["rest_interval_min"] = _clamp(self.rest_min_var.get(), 10, 240)
        cfg["rest_snooze_min"] = _clamp(self.snooze_var.get(), 5, 60)
        cfg["mood_check_min"] = _clamp(self.mood_var.get(), 30, 480)
        cfg["pet_height"] = _clamp(self.height_var.get(), 100, 320)
        cfg["user_name"] = self.name_var.get().strip() or "你"
        cfg["llm"] = self._collect_llm()
        config.save_config(cfg)
        try:
            autostart.set_enabled(cfg["autostart"])
        except RuntimeError as exc:
            messagebox.showwarning("开机自启动设置失败", str(exc), parent=self.win)
        self.app.apply_config()
        self.close()

    def close(self) -> None:
        self.app.settings = None
        if self.win.winfo_exists():
            self.win.destroy()


def _clamp(value, low: int, high: int) -> int:
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return low
