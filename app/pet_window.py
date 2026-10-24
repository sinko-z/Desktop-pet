"""桌面上的宠物窗口：无边框透明、置顶、呼吸动画、拖拽、右键菜单与喂食互动。"""

from __future__ import annotations

import math
import random
import time
import tkinter as tk

from PIL import Image, ImageOps, ImageTk

from . import dialogue, storage, ui
from .bubble import SpeechBubble, TRANSPARENT_KEY

FOODS = {
    "小饼干": (18, 4, "咔嚓咔嚓，好吃！"),
    "苹果": (22, 6, "脆脆的，谢谢你。"),
    "牛奶": (14, 4, "温温的，好舒服。"),
    "小鱼干": (26, 8, "这个我最喜欢啦！"),
}


def _solid_alpha(image: Image.Image) -> Image.Image:
    """把半透明边缘改成硬边。透明色键窗口里半透明像素会与键色混出描边，必须去掉。"""
    alpha = image.getchannel("A").point(lambda value: 255 if value >= 100 else 0)
    image.putalpha(alpha)
    return image


class PetWindow:
    def __init__(self, app):
        self.app = app
        self.root: tk.Tk = app.root
        self.win = tk.Toplevel(self.root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", bool(app.config["always_on_top"]))
        self.win.configure(bg=TRANSPARENT_KEY)
        try:
            self.win.wm_attributes("-transparentcolor", TRANSPARENT_KEY)
        except tk.TclError:
            pass

        self.canvas = tk.Canvas(self.win, bg=TRANSPARENT_KEY, highlightthickness=0, bd=0,
                                cursor="hand2")
        self.canvas.pack()

        self.bubble = SpeechBubble(self.root)
        self.frames: list[ImageTk.PhotoImage] = []
        self.frames_flip: list[ImageTk.PhotoImage] = []
        self.squash_frame: ImageTk.PhotoImage | None = None
        self.item = None
        self.phase = 0.0
        self.flipped = False
        self.squash_until = 0.0
        self.dragging = False
        self.drag_offset = (0, 0)
        self.drag_moved = False
        self.cw = self.ch = 0

        self._bind_events()
        self._build_menu()
        self.load_frames()
        self._tick()
        self._schedule_wander()

    # ---------- 形象与窗口 ----------
    def load_frames(self) -> None:
        pet = self.app.pet
        if not pet:
            self.win.withdraw()
            return
        path = storage.pet_image_path(pet)
        if not path.exists():
            self.win.withdraw()
            return
        image = Image.open(path).convert("RGBA")
        height = max(80, min(400, int(self.app.config["pet_height"])))
        ratio = height / image.height
        base = image.resize((max(1, int(image.width * ratio)), height), Image.LANCZOS)
        base = _solid_alpha(base)

        pil_frames = []
        steps = 12
        for index in range(steps):
            factor = 1 + 0.024 * math.sin(2 * math.pi * index / steps)
            size = (max(1, int(base.width * factor)), max(1, int(base.height * factor)))
            pil_frames.append(_solid_alpha(base.resize(size, Image.LANCZOS)))
        self.frames = [ImageTk.PhotoImage(frame) for frame in pil_frames]
        self.frames_flip = [ImageTk.PhotoImage(ImageOps.mirror(frame)) for frame in pil_frames]
        squash = base.resize((int(base.width * 1.08), int(base.height * 0.90)), Image.LANCZOS)
        self.squash_frame = ImageTk.PhotoImage(_solid_alpha(squash))

        self.cw = max(photo.width() for photo in self.frames) + 12
        self.ch = max(photo.height() for photo in self.frames) + 14
        self.canvas.configure(width=self.cw, height=self.ch)
        self.cx, self.cy = self.cw // 2, self.ch // 2 + 1
        if self.item is not None:
            self.canvas.delete(self.item)
        self.item = self.canvas.create_image(self.cx, self.cy, image=self.frames[0])

        screen_w = self.win.winfo_screenwidth()
        screen_h = self.win.winfo_screenheight()
        pos = self.app.config.get("pet_pos")
        if isinstance(pos, (list, tuple)) and len(pos) == 2:
            x, y = int(pos[0]), int(pos[1])
        else:
            x, y = screen_w - self.cw - 80, screen_h - self.ch - 90
        x = max(0, min(x, screen_w - self.cw))
        y = max(0, min(y, screen_h - self.ch - 40))
        self.win.geometry(f"{self.cw}x{self.ch}+{x}+{y}")
        self.win.deiconify()
        self.win.attributes("-topmost", bool(self.app.config["always_on_top"]))

    def apply_settings(self) -> None:
        self.win.attributes("-topmost", bool(self.app.config["always_on_top"]))
        self.load_frames()

    # ---------- 动画 ----------
    def _tick(self) -> None:
        if not self.win.winfo_exists():
            return
        self.phase += 0.09
        bob = 0 if self.dragging else 2.2 * math.sin(self.phase * 0.8)
        sway = 0 if self.dragging else 1.4 * math.sin(self.phase * 0.45)
        if time.time() < self.squash_until and self.squash_frame is not None:
            photo = self.squash_frame
        else:
            index = int((math.sin(self.phase) + 1) / 2 * (len(self.frames) - 1))
            photo = (self.frames_flip if self.flipped else self.frames)[index]
        self.canvas.itemconfigure(self.item, image=photo)
        self.canvas.coords(self.item, self.cx + sway, self.cy + bob)
        self.root.after(50, self._tick)

    def squash(self, seconds: float = 0.9) -> None:
        self.squash_until = time.time() + seconds

    # ---------- 交互 ----------
    def _bind_events(self) -> None:
        self.canvas.bind("<Button-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        self.canvas.bind("<Double-Button-1>", lambda _e: self.app.open_chat())
        self.canvas.bind("<Button-3>", self._popup)

    def _press(self, event) -> None:
        self.bubble.hide()
        self.dragging = True
        self.drag_moved = False
        self.drag_offset = (event.x_root - self.win.winfo_x(), event.y_root - self.win.winfo_y())

    def _drag(self, event) -> None:
        if not self.dragging:
            return
        x = event.x_root - self.drag_offset[0]
        y = event.y_root - self.drag_offset[1]
        if abs(x - self.win.winfo_x()) + abs(y - self.win.winfo_y()) > 3:
            self.drag_moved = True
        self.win.geometry(f"+{x}+{y}")

    def _release(self, _event) -> None:
        self.dragging = False
        if self.drag_moved:
            self._remember_position()
        else:
            self.stroke()

    def _remember_position(self) -> None:
        self.app.config["pet_pos"] = [self.win.winfo_x(), self.win.winfo_y()]
        self.app.save_config()

    def _popup(self, event) -> None:
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    def _build_menu(self) -> None:
        self.menu = tk.Menu(self.win, tearoff=0, font=ui.font(10))
        self.menu.add_command(label="和我聊天", command=lambda: self.app.open_chat())
        feed_menu = tk.Menu(self.menu, tearoff=0, font=ui.font(10))
        for food in FOODS:
            feed_menu.add_command(label=f"喂它{food}", command=lambda name=food: self.feed(name))
        self.menu.add_cascade(label="喂食", menu=feed_menu)
        self.menu.add_command(label="摸摸头", command=self.stroke)
        self.menu.add_command(label="查看状态", command=self.show_status)
        self.menu.add_separator()
        self.menu.add_command(label="给宠物取名…", command=self.app.rename_active_pet)
        self.menu.add_command(label="换个宠物…", command=self.app.open_manage)
        self.menu.add_command(label="添加新宠物…", command=self.app.open_create)
        self.menu.add_command(label="设置…", command=self.app.open_settings)
        self.menu.add_separator()
        self.menu.add_command(label="退出", command=self.app.quit)

    def stroke(self) -> None:
        pet = self.app.pet
        if not pet:
            return
        self.app.store.stroke(pet["id"])
        self.squash(0.5)
        self.say(random.choice(dialogue.PETTED_LINES), duration=3200)

    def feed(self, food: str) -> None:
        pet = self.app.pet
        if not pet:
            return
        amount, mood, line = FOODS[food]
        stats = self.app.store.feed(pet["id"], amount, mood)
        self.squash(0.9)
        self.say(f"{line}（饱腹 {int(stats['hunger'])}）", duration=4200)

    def show_status(self) -> None:
        pet = self.app.pet
        if not pet:
            return
        stats = self.app.store.stats_for(pet["id"])
        self.say(
            f"饱腹 {int(stats['hunger'])} · 心情 {int(stats['mood'])} · 亲密 {int(stats['affection'])}",
            duration=5200,
        )

    def say(self, text: str, duration: int = 6500, on_click=None) -> None:
        if not self.win.winfo_exists() or not self.win.winfo_ismapped():
            return
        x = self.win.winfo_x() + self.cw // 2
        y = self.win.winfo_y() + 2
        self.bubble.show(text, x, y, on_click=on_click, duration=duration)

    # ---------- 随机走动 ----------
    def _schedule_wander(self) -> None:
        self.root.after(random.randint(35000, 65000), self._wander)

    def _wander(self) -> None:
        if (self.app.config["wander"] and not self.dragging and not self.bubble.visible()
                and self.win.winfo_exists()):
            direction = random.choice((-1, 1))
            self.flipped = direction < 0
            self._wander_step(direction, random.randint(35, 95), 10)
        self._schedule_wander()

    def _wander_step(self, direction: int, total: int, steps: int) -> None:
        if steps <= 0 or not self.win.winfo_exists():
            self._remember_position()
            return
        screen_w = self.win.winfo_screenwidth()
        x = self.win.winfo_x() + direction * max(1, total // 10)
        x = max(0, min(x, screen_w - self.cw))
        self.win.geometry(f"+{x}+{self.win.winfo_y()}")
        self.root.after(65, lambda: self._wander_step(direction, total, steps - 1))

    def destroy(self) -> None:
        self.bubble.hide()
        if self.win.winfo_exists():
            self.win.destroy()
