"""上传照片生成专属宠物：实时预览抠图效果，确认后保存为新的宠物形象。"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from . import imaging, ui

PREVIEW_BOX = (400, 430)


class CreatePetWindow:
    def __init__(self, app):
        self.app = app
        self.root: tk.Tk = app.root
        self.source: Image.Image | None = None
        self.source_path: str = ""
        self.preview_img: ImageTk.PhotoImage | None = None
        self._job: str | None = None

        self.win = tk.Toplevel(self.root)
        self.win.title("生成我的专属宠物")
        self.win.configure(bg=ui.BG)
        ui.center_window(self.win, 900, 780)
        self.win.minsize(840, 720)
        self.win.protocol("WM_DELETE_WINDOW", self.close)

        self.mode_var = tk.StringVar(value="cutout")
        self.tolerance = tk.DoubleVar(value=48)
        self.feather = tk.DoubleVar(value=12)
        self.name_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="先选一张照片吧")

        self._build()

    def _build(self) -> None:
        wrap = tk.Frame(self.win, bg=ui.BG)
        wrap.pack(fill="both", expand=True, padx=24, pady=20)

        left = tk.Frame(wrap, bg=ui.CARD)
        left.pack(side="left", fill="both", expand=True)
        self.canvas = tk.Canvas(left, width=PREVIEW_BOX[0], height=PREVIEW_BOX[1],
                                bg="#EDE7DD", highlightthickness=0, bd=0)
        self.canvas.pack(padx=14, pady=14)
        self.canvas.create_text(PREVIEW_BOX[0] // 2, PREVIEW_BOX[1] // 2,
                                text="照片预览（透明区域显示为浅灰）",
                                font=ui.font(10), fill=ui.MUTED, width=280)

        right = tk.Frame(wrap, bg=ui.BG)
        right.pack(side="left", fill="both", expand=True, padx=(20, 0))

        ui.label(right, "上传一张照片", 15, True).pack(anchor="w")
        ui.label(right, "建议主体清晰、背景相对干净：宠物、玩偶或人像都可以。\n"
                       "程序会在本地完成抠图，不上传任何照片。",
                 9, fg=ui.MUTED).pack(anchor="w", pady=(6, 14))

        ui.primary(right, "选择照片…", self._pick).pack(anchor="w")
        self.file_label = ui.label(right, "尚未选择文件", 9, fg=ui.MUTED)
        self.file_label.pack(anchor="w", pady=(8, 16))

        mode_box = tk.Frame(right, bg=ui.CARD, padx=14, pady=12)
        mode_box.pack(fill="x")
        ui.label(mode_box, "形象方式", 10, True, bg=ui.CARD).pack(anchor="w")
        tk.Radiobutton(mode_box, text="自动抠图（推荐）", variable=self.mode_var, value="cutout",
                       command=self._schedule_render, bg=ui.CARD, activebackground=ui.CARD,
                       font=ui.font(9), anchor="w").pack(fill="x", pady=(6, 0))
        tk.Radiobutton(mode_box, text="保留原图卡片（复杂背景时使用）", variable=self.mode_var,
                       value="card", command=self._schedule_render, bg=ui.CARD,
                       activebackground=ui.CARD, font=ui.font(9), anchor="w").pack(fill="x")

        tol_row = tk.Frame(right, bg=ui.BG)
        tol_row.pack(fill="x", pady=(14, 0))
        ui.label(tol_row, "抠图容差", 9, fg=ui.MUTED).pack(side="left")
        self.tol_value = ui.label(tol_row, "48", 9)
        self.tol_value.pack(side="right")
        self.tol_scale = ttk.Scale(right, from_=0, to=100, variable=self.tolerance,
                                   command=lambda _v: self._update_labels())
        self.tol_scale.pack(fill="x")

        feather_row = tk.Frame(right, bg=ui.BG)
        feather_row.pack(fill="x", pady=(10, 0))
        ui.label(feather_row, "边缘羽化", 9, fg=ui.MUTED).pack(side="left")
        self.feather_value = ui.label(feather_row, "12", 9)
        self.feather_value.pack(side="right")
        self.feather_scale = ttk.Scale(right, from_=0, to=30, variable=self.feather,
                                       command=lambda _v: self._update_labels())
        self.feather_scale.pack(fill="x")
        ui.label(right, "背景去不干净就调高容差；边缘发毛就调低羽化。", 8, fg=ui.MUTED).pack(anchor="w")

        self.tolerance.trace_add("write", lambda *_: self._schedule_render())
        self.feather.trace_add("write", lambda *_: self._schedule_render())

        ui.label(right, "宠物名字", 9, fg=ui.MUTED).pack(anchor="w", pady=(14, 4))
        tk.Entry(right, textvariable=self.name_var, font=ui.font(10), bg=ui.CARD, fg=ui.INK,
                 relief="flat", highlightthickness=1, highlightbackground=ui.LINE,
                 highlightcolor=ui.ACCENT).pack(fill="x", ipady=7)

        self.create_btn = ui.primary(right, "生成宠物", self._create)
        self.create_btn.pack(fill="x", pady=(18, 6))
        self.status_label = ui.label(right, self.status_var.get(), 9, fg=ui.MUTED)
        self.status_label.pack(anchor="w")
        self.status_var.trace_add("write", lambda *_: self.status_label.configure(text=self.status_var.get()))

        ui.ghost(right, "取消", self.close).pack(anchor="e", pady=(8, 0))

    # ---------- 选择与预览 ----------
    def _pick(self) -> None:
        path = filedialog.askopenfilename(
            title="选择宠物照片",
            filetypes=[("图片", "*.png *.jpg *.jpeg *.webp *.bmp"), ("所有文件", "*.*")],
        )
        if not path:
            return
        try:
            self.source = imaging.load_image(path, max_side=900)
        except Exception as exc:  # noqa: BLE001 - 用户可能选了损坏的文件
            messagebox.showerror("无法读取图片", str(exc), parent=self.win)
            return
        self.source_path = path
        self.file_label.configure(text=Path(path).name, fg=ui.INK)
        if not self.name_var.get().strip():
            self.name_var.set(Path(path).stem[:12])
        self._render()

    def _update_labels(self) -> None:
        self.tol_value.configure(text=str(int(round(self.tolerance.get()))))
        self.feather_value.configure(text=str(int(round(self.feather.get()))))

    def _schedule_render(self, *_args) -> None:
        if self._job is not None:
            self.win.after_cancel(self._job)
        self._job = self.win.after(200, self._render)

    def _render(self) -> None:
        self._job = None
        if self.source is None:
            return
        mode = self.mode_var.get()
        self.status_var.set("正在处理…")
        self.win.update_idletasks()
        try:
            image = imaging.build_pet(
                self.source, mode, int(self.tolerance.get()),
                float(self.feather.get()) / 10.0, max_side=560,
            )
        except Exception as exc:  # noqa: BLE001
            self.status_var.set(f"处理失败：{exc}")
            return
        image.thumbnail(PREVIEW_BOX, Image.LANCZOS)
        self.preview_img = ImageTk.PhotoImage(image)
        self.canvas.delete("all")
        self.canvas.create_image(PREVIEW_BOX[0] // 2, PREVIEW_BOX[1] // 2,
                                 image=self.preview_img)
        self.status_var.set("预览已更新" if mode == "cutout" else "已切换为原图卡片")

    # ---------- 生成 ----------
    def _create(self) -> None:
        if self.source is None:
            messagebox.showinfo("还没有照片", "请先选择一张照片。", parent=self.win)
            return
        name = self.name_var.get().strip() or "小宠物"
        self.create_btn.configure(state="disabled", text="正在生成…")
        self.win.update_idletasks()
        try:
            image = imaging.build_pet(
                self.source, self.mode_var.get(), int(self.tolerance.get()),
                float(self.feather.get()) / 10.0, max_side=900,
            )
            pet = self.app.store.create_pet(name, image, self.mode_var.get(),
                                            Path(self.source_path).name)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("生成失败", str(exc), parent=self.win)
            self.create_btn.configure(state="normal", text="生成宠物")
            return
        self.app.set_active_pet(pet)
        self.app.config["onboarded"] = True
        self.app.save_config()
        self.close()
        self.app.pet_window.say(f"我是{pet['name']}，以后请多关照啦。", duration=5200)

    def close(self) -> None:
        if not self.app.config.get("onboarded"):
            self.app.config["onboarded"] = True
            self.app.save_config()
        self.app.create = None
        if self.win.winfo_exists():
            self.win.destroy()
