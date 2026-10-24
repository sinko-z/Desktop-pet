"""统一的配色、字体与少量复用控件，避免各个窗口重复样式代码。"""

from __future__ import annotations

import tkinter as tk

BG = "#F6F2EA"
CARD = "#FFFFFF"
INK = "#3B3730"
MUTED = "#8C8478"
LINE = "#E6DED1"
ACCENT = "#E2916B"
ACCENT_DARK = "#C9764F"
SOFT = "#F0E7DA"

FONT_FAMILY = "Microsoft YaHei UI"


def font(size: int = 10, bold: bool = False):
    return (FONT_FAMILY, size, "bold" if bold else "normal")


def center_window(win: tk.Toplevel, width: int, height: int) -> None:
    win.update_idletasks()
    x = max(0, (win.winfo_screenwidth() - width) // 2)
    y = max(0, (win.winfo_screenheight() - height) // 2 - 20)
    win.geometry(f"{width}x{height}+{x}+{y}")


def primary(parent, text: str, command) -> tk.Button:
    return tk.Button(
        parent, text=text, command=command, font=font(10, True),
        bg=ACCENT, fg="#FFFFFF", activebackground=ACCENT_DARK, activeforeground="#FFFFFF",
        relief="flat", bd=0, padx=16, pady=7, cursor="hand2",
    )


def ghost(parent, text: str, command) -> tk.Button:
    return tk.Button(
        parent, text=text, command=command, font=font(9),
        bg=CARD, fg=INK, activebackground=SOFT, activeforeground=INK,
        relief="flat", bd=0, highlightthickness=1, highlightbackground=LINE,
        padx=10, pady=4, cursor="hand2",
    )


def label(parent, text: str, size: int = 10, bold: bool = False,
          fg: str = INK, bg: str = BG, **kwargs) -> tk.Label:
    return tk.Label(parent, text=text, font=font(size, bold), fg=fg, bg=bg, **kwargs)


class ScrollFrame(tk.Frame):
    """带垂直滚动条的容器：内容放进 .inner。"""

    def __init__(self, master, bg: str = BG):
        super().__init__(master, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.bar = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self._window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.bar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.bar.pack(side="right", fill="y")
        self.inner.bind("<Configure>", self._sync)
        self.canvas.bind("<Configure>", self._fit_width)
        self.winfo_toplevel().bind("<MouseWheel>", self._on_wheel, add="+")

    def _sync(self, _event=None) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _fit_width(self, event) -> None:
        self.canvas.itemconfigure(self._window, width=event.width)

    def _on_wheel(self, event) -> None:
        self.canvas.yview_scroll(int(-event.delta / 120), "units")
