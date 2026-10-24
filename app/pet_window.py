"""桌面上的宠物窗口：透明置顶、呼吸与走动动画、立体投影、小动作、拖拽与喂食。"""

from __future__ import annotations

import math
import random
import time
import tkinter as tk

from PIL import Image, ImageDraw, ImageFilter, ImageOps, ImageTk

from . import dialogue, storage, ui
from .bubble import SpeechBubble, TRANSPARENT_KEY

FOODS = {
    "小饼干": (18, 4, "咔嚓咔嚓，好吃！"),
    "苹果": (22, 6, "脆脆的，谢谢你。"),
    "牛奶": (14, 4, "温温的，好舒服。"),
    "小鱼干": (26, 8, "这个我最喜欢啦！"),
}

ACTIONS = ("jump", "look", "shake", "stretch", "sit")
ACTION_SECONDS = {"jump": 0.6, "look": 2.2, "shake": 0.8, "stretch": 1.5, "sit": 3.4}

TOP_PAD = 4
BOTTOM_PAD = 28

# 透明色键窗口不能有半透明像素，投影用羽化后硬边化的椭圆近似柔和阴影
SHADOW_SCALES = (0.7, 0.8, 0.9, 1.0, 1.08)


def _solid_alpha(image: Image.Image) -> Image.Image:
    """把半透明边缘改成硬边。透明色键窗口里半透明像素会与键色混出描边，必须去掉。"""
    alpha = image.getchannel("A").point(lambda value: 255 if value >= 100 else 0)
    image.putalpha(alpha)
    return image


def _shadow_image(width: int, height: int) -> Image.Image:
    """椭圆羽化后按阈值硬边化：视觉上是柔和的一团，又不会与透明色键混出描边。"""
    mask = Image.new("L", (width, height), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, width - 1, height - 1), fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(max(1.5, height * 0.13)))
    mask = mask.point(lambda value: 255 if value > 96 else 0)
    shadow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    shadow.paste(Image.new("RGBA", (width, height), (100, 94, 86, 255)), (0, 0), mask)
    return shadow


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
        self.item = None
        self.shadow = None
        self.current_frame: ImageTk.PhotoImage | None = None
        self.squash_frame: ImageTk.PhotoImage | None = None
        self.idle_frames: list[ImageTk.PhotoImage] = []
        self.phase = 0.0
        self.flipped = False
        self.squash_until = 0.0
        self.dragging = False
        self.drag_offset = (0, 0)
        self.drag_moved = False
        self.cw = self.ch = 0
        self.cx = self.cy = 0
        self.frame_w = self.frame_h = 0
        self.feet_y = 0

        # 动画状态：idle / walk / act，拖拽时由 dragging 单独接管
        self.state = "idle"
        self.walk_dir = 1
        self.walk_left = 0.0
        self.action = ""
        self.action_started = 0.0
        self.action_until = 0.0
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.shadow_scale = 1.0
        self._action_job: str | None = None
        self._tick_job: str | None = None

        self._bind_events()
        self._build_menu()
        self.load_frames()
        self._tick()
        self._schedule_action()

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

        idle = []
        steps = 12
        for index in range(steps):
            factor = 1 + 0.024 * math.sin(2 * math.pi * index / steps)
            idle.append(self._scaled(base, factor, factor))
        tilt = [self._rotated(base, angle) for angle in (-5, 0, 5)]
        side = self._scaled(base, 0.86, 1.0)
        stretch = self._scaled(base, 0.94, 1.09)
        jump = self._scaled(base, 0.91, 1.12)
        crouch = self._scaled(base, 1.10, 0.88)

        raw = idle + tilt + [side, stretch, jump, crouch]
        self.frame_w = max(frame.width for frame in raw) + 8
        self.frame_h = max(frame.height for frame in raw) + 8
        self.cw = self.frame_w + 28
        self.ch = self.frame_h + TOP_PAD + BOTTOM_PAD
        self.cx = self.cw // 2
        self.cy = TOP_PAD + self.frame_h // 2
        self.feet_y = TOP_PAD + self.frame_h

        def photos(images):
            return [ImageTk.PhotoImage(self._anchor(frame, self.frame_w, self.frame_h))
                    for frame in images]

        self.idle_frames = photos(idle)
        self.idle_flip = photos([ImageOps.mirror(frame) for frame in idle])
        self.tilt_frames = photos(tilt)
        self.tilt_flip = photos([ImageOps.mirror(frame) for frame in tilt])
        self.side_l, self.side_r = photos([side, ImageOps.mirror(side)])
        self.stretch_frame = photos([stretch])[0]
        self.stretch_flip = photos([ImageOps.mirror(stretch)])[0]
        self.jump_frame = photos([jump])[0]
        self.jump_flip = photos([ImageOps.mirror(jump)])[0]
        self.crouch_frame = photos([crouch])[0]
        self.crouch_flip = photos([ImageOps.mirror(crouch)])[0]
        self.squash_frame = self.crouch_frame

        self.state = "idle"
        self.squash_until = 0.0
        self.current_frame = self.idle_frames[0]
        self.canvas.configure(width=self.cw, height=self.ch)
        self.canvas.delete("all")
        # 地面投影：抖动硬 alpha 图，随跳跃/走动缩放
        shadow_w = max(20, int(self.frame_w * 0.5))
        shadow_h = max(9, int(self.frame_h * 0.075))
        self.shadow_cache = {
            scale: ImageTk.PhotoImage(
                _shadow_image(max(12, int(shadow_w * scale)), max(6, int(shadow_h * scale))))
            for scale in SHADOW_SCALES
        }
        self.shadow = self.canvas.create_image(self.cx, self.feet_y + 6, image=self.shadow_cache[1.0])
        self.item = self.canvas.create_image(self.cx, self.cy, image=self.current_frame)
        self._update_shadow()

        screen_w = self.win.winfo_screenwidth()
        screen_h = self.win.winfo_screenheight()
        pos = self.app.config.get("pet_pos")
        if isinstance(pos, (list, tuple)) and len(pos) == 2:
            x, y = int(pos[0]), int(pos[1])
        else:
            x, y = screen_w - self.cw - 80, screen_h - self.ch - 90
        x = max(4, min(x, screen_w - self.cw - 4))
        y = max(0, min(y, screen_h - self.ch - 40))
        self.win.geometry(f"{self.cw}x{self.ch}+{x}+{y}")
        self.win.deiconify()
        self.win.attributes("-topmost", bool(self.app.config["always_on_top"]))

    def apply_settings(self) -> None:
        self.win.attributes("-topmost", bool(self.app.config["always_on_top"]))
        self.load_frames()

    @staticmethod
    def _scaled(base: Image.Image, width_factor: float, height_factor: float) -> Image.Image:
        size = (max(1, int(base.width * width_factor)), max(1, int(base.height * height_factor)))
        return _solid_alpha(base.resize(size, Image.LANCZOS))

    @staticmethod
    def _rotated(base: Image.Image, angle: float) -> Image.Image:
        return _solid_alpha(base.rotate(angle, resample=Image.BICUBIC, expand=True))

    @staticmethod
    def _anchor(image: Image.Image, width: int, height: int) -> Image.Image:
        """统一画布，底部居中对齐，保证所有动作的“脚”都踩在同一条线上。"""
        canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        canvas.paste(image, ((width - image.width) // 2, height - image.height), image)
        return canvas

    def _update_shadow(self) -> None:
        if self.shadow is None:
            return
        scale = min(SHADOW_SCALES, key=lambda value: abs(value - self.shadow_scale))
        self.canvas.itemconfigure(self.shadow, image=self.shadow_cache[scale])
        self.canvas.coords(self.shadow, self.cx + self.offset_x * 0.6, self.feet_y + 3)

    # ---------- 动画 ----------
    def _tick(self) -> None:
        if not self.win.winfo_exists():
            return
        if not self.idle_frames:
            # 没有可用形象（例如图片被删）时先停下，等重新加载
            self._tick_job = self.root.after(500, self._tick)
            return
        self.phase += 0.09
        now = time.time()
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.shadow_scale = 1.0

        if self.dragging:
            self.current_frame = self.idle_frames[0]
        elif self.state == "walk":
            self._walk_tick()
        elif self.state == "act":
            self._act_tick(now)
        else:
            self._idle_tick()

        photo = self.squash_frame if now < self.squash_until else self.current_frame
        self.canvas.itemconfigure(self.item, image=photo or self.idle_frames[0])
        self.canvas.coords(self.item, self.cx + self.offset_x, self.cy + self.offset_y)
        self._update_shadow()
        self._tick_job = self.root.after(50, self._tick)

    def _idle_tick(self) -> None:
        index = int((math.sin(self.phase) + 1) / 2 * (len(self.idle_frames) - 1))
        frames = self.idle_flip if self.flipped else self.idle_frames
        self.current_frame = frames[index]
        self.offset_y = 2.2 * math.sin(self.phase * 0.8)
        self.offset_x = 1.4 * math.sin(self.phase * 0.45)

    def _walk_tick(self) -> None:
        hop = abs(math.sin(self.phase * 2.2)) * 5
        self.offset_y = -hop
        self.shadow_scale = max(0.55, 1 - hop / 16)
        index = 0 if int(self.phase * 5) % 2 == 0 else 2
        frames = self.tilt_flip if self.walk_dir < 0 else self.tilt_frames
        self.current_frame = frames[index]
        self.offset_x = self.walk_dir * 1.0

        screen_w = self.win.winfo_screenwidth()
        limit = max(4, screen_w - self.cw - 4)
        x = self.win.winfo_x()
        if x < 4 or x > limit:
            # 从屏幕外或贴边状态走回来
            x = max(4, min(x, limit))
            self.win.geometry(f"+{x}+{self.win.winfo_y()}")
        new_x = x + self.walk_dir * 3
        if new_x < 4 or new_x > limit:
            # 走到屏幕边缘就掉头
            self.walk_dir *= -1
            self.flipped = self.walk_dir < 0
            new_x = max(4, min(x + self.walk_dir * 3, limit))
        self.win.geometry(f"+{new_x}+{self.win.winfo_y()}")
        self.walk_left -= abs(new_x - x)
        if self.walk_left <= 0:
            self.state = "idle"
            self.flipped = self.walk_dir < 0
            self._remember_position()

    def _act_tick(self, now: float) -> None:
        elapsed = now - self.action_started
        duration = max(0.001, self.action_until - self.action_started)
        progress = min(1.0, elapsed / duration)
        name = self.action

        if name == "jump":
            lift = math.sin(math.pi * progress)
            self.offset_y = -lift * 30
            self.shadow_scale = 1 - 0.3 * lift
            self.current_frame = self.jump_flip if self.flipped else self.jump_frame
        elif name == "look":
            aside = 1 if int(elapsed / 0.55) % 2 == 0 else -1
            self.current_frame = self.side_r if aside > 0 else self.side_l
            self.offset_x = aside * 3
        elif name == "shake":
            self.offset_x = math.sin(elapsed * 28) * 5
            self.current_frame = self.idle_frames[0]
        elif name == "stretch":
            if progress < 0.7:
                self.current_frame = self.stretch_frame
                self.offset_y = -2.0
            else:
                self.current_frame = self.idle_frames[0]
        else:  # sit
            self.current_frame = self.crouch_flip if self.flipped else self.crouch_frame
            self.shadow_scale = 1.08
            self.offset_y = 1.0

        if progress >= 1.0:
            self.state = "idle"
            self.action = ""

    def squash(self, seconds: float = 0.9) -> None:
        self.squash_until = time.time() + seconds

    # ---------- 小动作与随机走动 ----------
    def _schedule_action(self) -> None:
        if self._action_job is not None:
            try:
                self.root.after_cancel(self._action_job)
            except tk.TclError:
                pass
        self._action_job = self.root.after(random.randint(15000, 32000), self._ambient)

    def _ambient(self) -> None:
        self._action_job = None
        if self.state == "idle" and not self.dragging and not self.bubble.visible():
            if self.app.config["wander"] and random.random() < 0.45:
                self._start_walk()
            else:
                self._start_action(random.choice(ACTIONS))
        self._schedule_action()

    def _start_walk(self) -> None:
        if self.state != "idle" or self.dragging:
            return
        self.state = "walk"
        self.walk_dir = random.choice((-1, 1))
        self.walk_left = float(random.randint(45, 150))
        self.flipped = self.walk_dir < 0

    def _start_action(self, name: str) -> None:
        if self.state == "walk" or self.dragging:
            return
        self.action = name
        self.action_started = time.time()
        self.action_until = self.action_started + ACTION_SECONDS[name]
        self.state = "act"

    def perform_trick(self) -> None:
        if self.state == "idle" and not self.dragging:
            self._start_action(random.choice(ACTIONS))
            return
        self.squash(0.4)

    # ---------- 交互 ----------
    def _bind_events(self) -> None:
        self.canvas.bind("<Button-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        self.canvas.bind("<Double-Button-1>", lambda _e: self.app.open_chat())
        self.canvas.bind("<Button-3>", self._popup)

    def _press(self, event) -> None:
        self.bubble.hide()
        if self.state == "walk":
            self.state = "idle"
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
        self.state = "idle"
        if self.drag_moved:
            self._remember_position()
            self.squash(0.35)   # 落地时压一下，像真的被放回桌面
        else:
            self.stroke()

    def _remember_position(self) -> None:
        self.app.config["pet_pos"] = [self.win.winfo_x(), self.win.winfo_y()]
        self.app.save_config()

    def _popup(self, event) -> None:
        if not self.win.winfo_exists():
            return
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            try:
                self.menu.grab_release()
            except tk.TclError:
                pass

    def _build_menu(self) -> None:
        self.menu = tk.Menu(self.win, tearoff=0, font=ui.font(10))
        self.menu.add_command(label="和我聊天", command=lambda: self.app.open_chat())
        feed_menu = tk.Menu(self.menu, tearoff=0, font=ui.font(10))
        for food in FOODS:
            feed_menu.add_command(label=f"喂它{food}", command=lambda name=food: self.feed(name))
        self.menu.add_cascade(label="喂食", menu=feed_menu)
        self.menu.add_command(label="摸摸头", command=self.stroke)
        self.menu.add_command(label="做个动作", command=self.perform_trick)
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
        if self.state == "idle":
            self._start_action("shake")
        self.squash(0.6)
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

    def destroy(self) -> None:
        for job in (self._action_job, self._tick_job):
            if job is not None:
                try:
                    self.root.after_cancel(job)
                except tk.TclError:
                    pass
        self._action_job = self._tick_job = None
        self.bubble.hide()
        if self.win.winfo_exists():
            self.win.destroy()
