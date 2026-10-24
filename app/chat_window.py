"""聊天陪伴窗口：心情快捷按钮、离线话术、可选大模型、深呼吸引导。"""

from __future__ import annotations

import queue
import threading
import tkinter as tk

from PIL import Image, ImageTk

from . import dialogue, storage, ui


class ChatWindow:
    def __init__(self, app, pet: dict, opening: str | None = None):
        self.app = app
        self.root: tk.Tk = app.root
        self.pet = pet
        self.history: list[dict] = [
            {"role": item["role"], "text": item["text"]}
            for item in app.store.history(pet["id"])[-20:]
        ]
        self._queue: queue.Queue = queue.Queue()
        self._waiting = False
        self._timers: list[str] = []

        self.win = tk.Toplevel(self.root)
        self.win.title(f"和 {pet['name']} 聊天")
        self.win.configure(bg=ui.BG)
        ui.center_window(self.win, 500, 640)
        self.win.minsize(440, 520)
        self.win.protocol("WM_DELETE_WINDOW", self.close)
        self._set_icon()

        self._build()
        self._load_history()
        if opening:
            self._append("pet", opening)
        elif not self.history:
            self._append("pet", dialogue.greeting(pet["name"], app.config["user_name"]))

    # ---------- 界面 ----------
    def _set_icon(self) -> None:
        try:
            thumb = Image.open(storage.pet_thumb_path(self.pet)).convert("RGBA")
            thumb.thumbnail((64, 64))
            self._icon = ImageTk.PhotoImage(thumb)
            self.win.iconphoto(False, self._icon)
        except OSError:
            pass

    def _build(self) -> None:
        header = tk.Frame(self.win, bg=ui.CARD)
        header.pack(fill="x")
        avatar = self._avatar()
        if avatar is not None:
            tk.Label(header, image=avatar, bg=ui.CARD).pack(side="left", padx=(16, 10), pady=12)
        text_box = tk.Frame(header, bg=ui.CARD)
        text_box.pack(side="left", pady=12)
        self.name_label = ui.label(text_box, self.pet["name"], 12, True, bg=ui.CARD)
        self.name_label.pack(anchor="w")
        self.status = ui.label(text_box, self._status_text(), 9, fg=ui.MUTED, bg=ui.CARD)
        self.status.pack(anchor="w")

        body = tk.Frame(self.win, bg=ui.BG)
        body.pack(fill="both", expand=True, padx=12, pady=(10, 0))
        self.text = tk.Text(body, wrap="word", height=8, bg="#FCFAF6", bd=0, highlightthickness=0,
                            padx=14, pady=12, font=ui.font(10), spacing1=2, spacing3=10,
                            cursor="arrow")
        scroll = tk.Scrollbar(body, command=self.text.yview)
        self.text.configure(yscrollcommand=scroll.set, state="disabled")
        self.text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.text.tag_configure("pet", foreground=ui.INK, justify="left")
        self.text.tag_configure("me", foreground=ui.ACCENT_DARK, justify="right")
        self.text.tag_configure("sys", foreground=ui.MUTED, justify="center", font=ui.font(9))

        chips = tk.Frame(self.win, bg=ui.BG)
        chips.pack(fill="x", padx=12, pady=(8, 0))
        for label, sentence in dialogue.QUICK_MOODS:
            ui.ghost(chips, label, lambda s=sentence: self.send(s)).pack(side="left", padx=(0, 6))

        input_row = tk.Frame(self.win, bg=ui.BG)
        input_row.pack(fill="x", padx=12, pady=(10, 8))
        self.entry = tk.Entry(input_row, font=ui.font(10), bg=ui.CARD, fg=ui.INK, relief="flat",
                              highlightthickness=1, highlightbackground=ui.LINE,
                              highlightcolor=ui.ACCENT)
        self.entry.pack(side="left", fill="x", expand=True, ipady=8, padx=(0, 8))
        self.entry.bind("<Return>", lambda _e: self.send())
        self.send_btn = ui.primary(input_row, "发送", self.send)
        self.send_btn.pack(side="right")

        footer = tk.Frame(self.win, bg=ui.BG)
        footer.pack(fill="x", padx=12, pady=(0, 10))
        ui.ghost(footer, "深呼吸放松", self.breathe).pack(side="left")
        self.mode_label = ui.label(footer, self._mode_text(), 9, fg=ui.MUTED)
        self.mode_label.pack(side="right")
        self.entry.focus_set()

    def _avatar(self):
        try:
            thumb = Image.open(storage.pet_thumb_path(self.pet)).convert("RGBA")
            thumb.thumbnail((48, 48))
            self._avatar_img = ImageTk.PhotoImage(thumb)
            return self._avatar_img
        except OSError:
            return None

    def _mode_text(self) -> str:
        llm = self.app.config["llm"]
        if llm.get("enabled") and llm.get("api_key") and llm.get("base_url") and llm.get("model"):
            return f"已接入大模型 · {llm.get('model', '')}"
        return "本地陪伴模式"

    def _status_text(self) -> str:
        stats = self.app.store.stats_for(self.pet["id"])
        return f"心情 {int(stats['mood'])} · 饱腹 {int(stats['hunger'])} · 亲密 {int(stats['affection'])}"

    def _refresh_status(self) -> None:
        if self.win.winfo_exists():
            self.status.configure(text=self._status_text())

    # ---------- 消息 ----------
    def _load_history(self) -> None:
        for item in self.history[-14:]:
            self._render(item["role"], item["text"])

    def _render(self, role: str, text: str) -> None:
        self.text.configure(state="normal")
        if role == "me":
            self.text.insert("end", f"我：{text}\n\n", "me")
        elif role == "sys":
            self.text.insert("end", f"{text}\n\n", "sys")
        else:
            self.text.insert("end", f"{self.pet['name']}：{text}\n\n", "pet")
        self.text.configure(state="disabled")
        self.text.see("end")

    def _append(self, role: str, text: str, persist: bool = False) -> None:
        self._render(role, text)
        if persist:
            self.history.append({"role": role, "text": text})
            self.app.store.add_chat(self.pet["id"], role, text)
        self._refresh_status()

    def send(self, text: str | None = None, persist: bool = True) -> None:
        if self._waiting:
            return
        content = (text if text is not None else self.entry.get()).strip()
        if not content:
            return
        self.entry.delete(0, "end")
        self._append("me", content, persist=persist)

        llm = self.app.config["llm"]
        use_llm = all(llm.get(k) for k in ("api_key", "base_url", "model")) and llm.get("enabled")
        if use_llm:
            self._waiting = True
            self.send_btn.configure(state="disabled", text="思考中")
            self.status.configure(text="正在输入…")
            snapshot = list(self.history)
            threading.Thread(
                target=self._ask_model,
                args=(snapshot, dict(llm)),
                daemon=True,
            ).start()
            self._poll()
        else:
            reply = dialogue.builtin_reply(content, self.pet["name"], self.app.config["user_name"])
            self._append("pet", reply, persist=persist)

    def _ask_model(self, history: list[dict], llm: dict) -> None:
        try:
            text, _source, error = dialogue.reply(
                history, self.pet["name"], self.app.config["user_name"], llm,
            )
        except Exception as exc:  # noqa: BLE001 - 线程里必须保证有结果回传
            last = next((m["text"] for m in reversed(history) if m["role"] == "me"), "")
            text = dialogue.builtin_reply(last, self.pet["name"], self.app.config["user_name"])
            error = str(exc)
        self._queue.put((text, error))

    def _poll(self) -> None:
        if not self.win.winfo_exists():
            return
        try:
            text, error = self._queue.get_nowait()
        except queue.Empty:
            self.win.after(120, self._poll)
            return
        self._waiting = False
        self.send_btn.configure(state="normal", text="发送")
        self.status.configure(text=self._status_text())
        self._append("pet", text, persist=True)
        if error:
            self._append("sys", f"（大模型暂时不可用，已用本地陪伴回答：{error}）")

    # ---------- 深呼吸 ----------
    def breathe(self) -> None:
        steps = [
            ("先把肩膀放松，坐舒服一点。", 0),
            ("用鼻子慢慢吸气，数 4 秒。", 1200),
            ("轻轻停住，数 2 秒。", 5200),
            ("用嘴慢慢呼气，数 6 秒。", 7200),
            ("很好，再做两轮。", 13200),
            ("做完感觉怎么样？想说什么都可以告诉我。", 20000),
        ]
        for line, delay in steps:
            self._timers.append(
                self.win.after(delay, lambda l=line: self._breathe_line(l))
            )

    def _breathe_line(self, line: str) -> None:
        if self.win.winfo_exists():
            self._render("pet", line)

    # ---------- 窗口 ----------
    def alive(self) -> bool:
        return self.win.winfo_exists()

    def focus(self) -> None:
        self.win.deiconify()
        self.win.lift()
        self.entry.focus_set()

    def refresh_name(self) -> None:
        self.win.title(f"和 {self.pet['name']} 聊天")
        self.name_label.configure(text=self.pet["name"])

    def prefill(self, opening: str) -> None:
        self._render("pet", opening)

    def close(self) -> None:
        for timer in self._timers:
            try:
                self.win.after_cancel(timer)
            except tk.TclError:
                pass
        self._timers.clear()
        self.app.chat = None
        if self.win.winfo_exists():
            self.win.destroy()
