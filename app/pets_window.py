"""历史宠物管理：查看、应用、改名、删除。"""

from __future__ import annotations

import time
import tkinter as tk
from tkinter import messagebox, simpledialog

from PIL import Image, ImageTk

from . import storage, ui


class PetsWindow:
    def __init__(self, app):
        self.app = app
        self.root: tk.Tk = app.root
        self.win = tk.Toplevel(self.root)
        self.win.title("我的宠物")
        self.win.configure(bg=ui.BG)
        ui.center_window(self.win, 760, 620)
        self.win.minsize(680, 480)
        self.win.protocol("WM_DELETE_WINDOW", self.close)
        self._thumbs: list[ImageTk.PhotoImage] = []

        header = tk.Frame(self.win, bg=ui.BG)
        header.pack(fill="x", padx=24, pady=(20, 8))
        ui.label(header, "我的宠物", 16, True).pack(side="left")
        ui.primary(header, "上传照片生成新宠物", self.app.open_create).pack(side="right")

        self.scroll = ui.ScrollFrame(self.win)
        self.scroll.pack(fill="both", expand=True, padx=20, pady=(0, 16))
        self.refresh()

    def refresh(self) -> None:
        for child in self.scroll.inner.winfo_children():
            child.destroy()
        self._thumbs.clear()
        self.app.store.pets = sorted(self.app.store.pets, key=lambda p: p["created_at"], reverse=True)
        for pet in self.app.store.pets:
            self._row(pet)

    def _row(self, pet: dict) -> None:
        card = tk.Frame(self.scroll.inner, bg=ui.CARD, padx=14, pady=12)
        card.pack(fill="x", pady=6)

        thumb_path = storage.pet_thumb_path(pet)
        if thumb_path.exists():
            image = Image.open(thumb_path).convert("RGBA")
            image.thumbnail((72, 72))
            photo = ImageTk.PhotoImage(image)
            self._thumbs.append(photo)
            tk.Label(card, image=photo, bg=ui.CARD).pack(side="left", padx=(0, 14))
        else:
            tk.Label(card, text="?", width=4, bg=ui.SOFT, font=ui.font(16, True)).pack(
                side="left", padx=(0, 14))

        info = tk.Frame(card, bg=ui.CARD)
        info.pack(side="left", fill="x", expand=True)
        title = pet["name"] + ("  · 正在使用" if pet["id"] == self.app.store.active_pet_id else "")
        ui.label(info, title, 11, True, bg=ui.CARD).pack(anchor="w")
        created = time.strftime("%Y-%m-%d %H:%M", time.localtime(pet["created_at"]))
        mode = "自动抠图" if pet["mode"] == "cutout" else (
            "原图卡片" if pet["mode"] == "card" else "内置形象")
        ui.label(info, f"{mode} · 创建于 {created}", 8, fg=ui.MUTED, bg=ui.CARD).pack(anchor="w", pady=(4, 0))

        actions = tk.Frame(card, bg=ui.CARD)
        actions.pack(side="right")
        if pet["id"] == self.app.store.active_pet_id:
            ui.label(actions, "使用中", 9, fg=ui.ACCENT_DARK, bg=ui.CARD).pack(side="left", padx=(0, 10))
        else:
            ui.ghost(actions, "使用", lambda p=pet: self._apply(p)).pack(side="left", padx=(0, 8))
        ui.ghost(actions, "改名", lambda p=pet: self._rename(p)).pack(side="left", padx=(0, 8))
        if len(self.app.store.pets) > 1:
            ui.ghost(actions, "删除", lambda p=pet: self._delete(p)).pack(side="left")

    def _apply(self, pet: dict) -> None:
        self.app.set_active_pet(pet)
        self.refresh()

    def _rename(self, pet: dict) -> None:
        name = simpledialog.askstring("改名", "给宠物起个新名字：", initialvalue=pet["name"],
                                      parent=self.win)
        if name and name.strip():
            self.app.store.rename_pet(pet["id"], name.strip()[:16])
            self.refresh()
            if pet["id"] == self.app.store.active_pet_id and self.app.chat:
                self.app.chat.close()

    def _delete(self, pet: dict) -> None:
        if not messagebox.askyesno("删除宠物", f"确定删除「{pet['name']}」吗？照片也会一起删除。",
                                   parent=self.win):
            return
        was_active = pet["id"] == self.app.store.active_pet_id
        self.app.store.delete_pet(pet["id"])
        self.refresh()
        if was_active:
            self.app.pet_window.load_frames()
            if self.app.chat:
                self.app.chat.close()

    def close(self) -> None:
        self.app.pets_win = None
        if self.win.winfo_exists():
            self.win.destroy()
