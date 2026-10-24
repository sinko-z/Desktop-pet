"""桌宠头顶的气泡。用透明色键 + Canvas 绘制，圆角外缘不会出现图片混色描边。"""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont

from . import ui

TRANSPARENT_KEY = "#FF00FE"


class SpeechBubble:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.win: tk.Toplevel | None = None
        self._timer = None

    def visible(self) -> bool:
        return self.win is not None and self.win.winfo_exists()

    def show(self, text: str, x: int, y: int, on_click=None, duration: int = 6500) -> None:
        """x/y 为气泡底部中点，一般是桌宠窗口顶部。"""
        self.hide()
        face = tkfont.Font(family=ui.FONT_FAMILY, size=10)
        max_width = 250
        lines = _wrap(text, face, max_width)
        line_height = face.metrics("linespace")
        text_width = max(face.measure(line) for line in lines) if lines else 0
        pad_x, pad_y, tail = 14, 11, 9
        width = max(130, text_width + pad_x * 2)
        height = len(lines) * line_height + pad_y * 2 + tail

        win = tk.Toplevel(self.root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        try:
            win.wm_attributes("-transparentcolor", TRANSPARENT_KEY)
        except tk.TclError:
            pass
        canvas = tk.Canvas(win, width=width, height=height, bg=TRANSPARENT_KEY,
                           highlightthickness=0, bd=0)
        canvas.pack()

        radius = 13
        # 小尾巴先画，再画气泡主体盖住接缝
        canvas.create_polygon(
            [width // 2 - 7, height - tail - 1, width // 2 + 7, height - tail - 1,
             width // 2, height - 2],
            fill=ui.CARD, outline="",
        )
        body_bottom = height - tail
        points = [
            radius, 0, width - radius, 0, width - radius, 0, width, 0, width, 0,
            width, radius, width, body_bottom - radius, width, body_bottom - radius,
            width, body_bottom, width, body_bottom, width - radius, body_bottom,
            radius, body_bottom, radius, body_bottom, 0, body_bottom, 0, body_bottom,
            0, body_bottom - radius, 0, radius, 0, radius, 0, 0, radius, 0,
        ]
        canvas.create_polygon(points, smooth=True, fill=ui.CARD, outline=ui.LINE)
        canvas.create_text(pad_x, pad_y, text="\n".join(lines), anchor="nw",
                           font=face, fill=ui.INK, justify="left")

        screen_w = win.winfo_screenwidth()
        left = max(8, min(x - width // 2, screen_w - width - 8))
        top = max(8, y - height + 4)
        win.geometry(f"{width}x{height}+{left}+{top}")

        canvas.bind("<Button-1>", lambda _e: self._click(on_click))
        self.win = win
        self._timer = self.root.after(duration, self.hide)

    def _click(self, callback) -> None:
        self.hide()
        if callback:
            callback()

    def hide(self) -> None:
        if self._timer is not None:
            try:
                self.root.after_cancel(self._timer)
            except tk.TclError:
                pass
            self._timer = None
        if self.win is not None and self.win.winfo_exists():
            self.win.destroy()
        self.win = None


def _wrap(text: str, face: tkfont.Font, max_width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for char in text:
        if char == "\n":
            lines.append(current)
            current = ""
            continue
        if current and face.measure(current + char) > max_width:
            lines.append(current)
            current = char
        else:
            current += char
    if current:
        lines.append(current)
    return lines or [""]
