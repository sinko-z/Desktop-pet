"""应用控制器：串联桌宠、提醒、聊天、宠物管理与设置窗口。"""

from __future__ import annotations

import random
import time
import tkinter as tk
from tkinter import simpledialog

from . import config, dialogue, imaging, reminder, storage
from .chat_window import ChatWindow
from .create_pet import CreatePetWindow
from .pet_window import PetWindow
from .pets_window import PetsWindow
from .settings_window import SettingsWindow


class Application:
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title("Desktop Pet")

        config.ensure_dirs()
        self.config = config.load_config()
        self.store = storage.Store()
        self._ensure_pet()

        self.pet_window = PetWindow(self)
        self.reminder = reminder.ActivityTracker()
        self.chat: ChatWindow | None = None
        self.create: CreatePetWindow | None = None
        self.pets_win: PetsWindow | None = None
        self.settings: SettingsWindow | None = None

        self._closing = False
        self._last_save = time.time()
        self._last_hungry = 0.0
        self._next_chatter = time.time() + random.randint(360, 720)

        self.root.after(700, self._startup)
        self.root.after(3000, self._heartbeat)

    # ---------- 启动 ----------
    def _ensure_pet(self) -> None:
        if not self.store.pets:
            self.store.create_pet("团子", imaging.make_default_pet(), mode="builtin",
                                  source="内置形象")

    def _startup(self) -> None:
        if not self.config.get("onboarded"):
            self.say("嗨，我是你的桌面宠物。先上传一张照片，让我变成你的专属样子吧。", 8000)
            self.root.after(900, self.open_create)
        else:
            self.say("我回来啦，右键点我可以聊天、喂食或设置。", 5200)

    # ---------- 主循环 ----------
    def _heartbeat(self) -> None:
        if self._closing:
            return
        try:
            for event in self.reminder.tick(self.config):
                if event == "rest":
                    minutes = int(self.config["rest_interval_min"])
                    self.say(
                        f"已经连续坐了 {minutes} 分钟啦。" + random.choice(dialogue.REST_LINES),
                        9000,
                        lambda: self.open_chat("刚刚坐了很久，肩膀有点僵吧？要不要先歇一歇？"),
                    )
                else:
                    self.say(random.choice(dialogue.MOOD_CHECK_LINES), 8000,
                             lambda: self.open_chat())
            pet = self.pet
            if pet:
                stats = self.store.decay(pet["id"])
                self._maybe_chatter(stats)
            if time.time() - self._last_save > 30:
                self.store.save_state()
                self._last_save = time.time()
        finally:
            if not self._closing:
                self.root.after(5000, self._heartbeat)

    def _maybe_chatter(self, stats: dict) -> None:
        now = time.time()
        if stats["hunger"] < 30 and now - self._last_hungry > 900:
            self._last_hungry = now
            self.say(random.choice(dialogue.HUNGRY_LINES), 6000)
            return
        if now >= self._next_chatter:
            self._next_chatter = now + random.randint(420, 900)
            if self.pet_window.bubble.visible() or self.pet_window.dragging:
                return
            self.say(random.choice(dialogue.IDLE_LINES), 4200)

    # ---------- 对外接口 ----------
    @property
    def pet(self) -> dict | None:
        return self.store.active_pet()

    def say(self, text: str, duration: int = 6500, on_click=None) -> None:
        self.pet_window.say(text, duration=duration, on_click=on_click)

    def save_config(self) -> None:
        config.save_config(self.config)

    def apply_config(self) -> None:
        self.pet_window.apply_settings()

    def set_active_pet(self, pet: dict) -> None:
        self.store.set_active(pet["id"])
        if self.chat and self.chat.alive():
            self.chat.close()
        self.pet_window.load_frames()
        if self.pets_win and self.pets_win.win.winfo_exists():
            self.pets_win.refresh()

    def rename_active_pet(self) -> None:
        pet = self.pet
        if not pet:
            return
        name = simpledialog.askstring(
            "给宠物取名", "新名字（最多 16 个字）：",
            initialvalue=pet["name"], parent=self.pet_window.win,
        )
        if not name or not name.strip():
            return
        name = name.strip()[:16]
        self.store.rename_pet(pet["id"], name)
        if self.chat and self.chat.alive():
            self.chat.refresh_name()
        if self.pets_win and self.pets_win.win.winfo_exists():
            self.pets_win.refresh()
        self.say(f"以后就叫我{name}啦。", 4200)

    def open_chat(self, opening: str | None = None) -> None:
        if not self.pet:
            return
        if self.chat and self.chat.alive():
            self.chat.focus()
            if opening:
                self.chat.prefill(opening)
            return
        self.chat = ChatWindow(self, self.pet, opening)

    def open_create(self) -> None:
        if self.create and self.create.win.winfo_exists():
            self.create.win.lift()
            self.create.win.focus_set()
            return
        self.create = CreatePetWindow(self)

    def open_manage(self) -> None:
        if self.pets_win and self.pets_win.win.winfo_exists():
            self.pets_win.win.lift()
            return
        self.pets_win = PetsWindow(self)

    def open_settings(self) -> None:
        if self.settings and self.settings.win.winfo_exists():
            self.settings.win.lift()
            return
        self.settings = SettingsWindow(self)

    # ---------- 生命周期 ----------
    def run(self) -> None:
        self.root.mainloop()

    def quit(self) -> None:
        self._closing = True
        try:
            self.store.save_state()
            self.save_config()
        finally:
            self.pet_window.destroy()
            self.root.destroy()
