"""把一张照片变成桌宠形象：前景抠图、边缘羽化、圆角卡片，以及内置的默认小宠物。"""

from __future__ import annotations

import statistics

from PIL import Image, ImageDraw, ImageFilter, ImageOps


def load_image(path: str, max_side: int = 900) -> Image.Image:
    """读取照片，按 EXIF 方向摆正，透明区域铺白底，再缩到可处理的大小。"""
    image = Image.open(path)
    image = ImageOps.exif_transpose(image)
    if image.mode in ("RGBA", "LA") or "transparency" in image.info:
        image = image.convert("RGBA")
        white = Image.new("RGBA", image.size, (255, 255, 255, 255))
        image = Image.alpha_composite(white, image)
    image = image.convert("RGB")
    image.thumbnail((max_side, max_side), Image.LANCZOS)
    return image


def build_pet(source: Image.Image, mode: str = "cutout", tolerance: int = 45,
              feather: float = 1.2, max_side: int = 900) -> Image.Image:
    image = source.convert("RGB").copy()
    image.thumbnail((max_side, max_side), Image.LANCZOS)
    if mode == "card":
        return _card(image)
    cut = _cutout(image, tolerance, feather)
    # 背景太复杂导致整张图被抠掉时，退回圆角卡片，避免生成空图
    if cut is None or cut.width < 16 or cut.height < 16:
        return _card(image)
    return cut


def _border_color(image: Image.Image) -> tuple[int, int, int]:
    """取四条边上的像素中位数作为“背景色”。"""
    width, height = image.size
    step = max(1, min(width, height) // 80)
    pixels = image.load()
    samples = []
    for x in range(0, width, step):
        samples.append(pixels[x, 0])
        samples.append(pixels[x, height - 1])
    for y in range(0, height, step):
        samples.append(pixels[0, y])
        samples.append(pixels[width - 1, y])
    return tuple(int(statistics.median(c[i] for c in samples)) for i in range(3))


def _cutout(image: Image.Image, tolerance: int, feather: float) -> Image.Image | None:
    width, height = image.size
    if width < 8 or height < 8:
        return None
    bg = _border_color(image)
    pixels = image.load()
    threshold = (8 + tolerance * 2.2) ** 2

    mask = Image.new("L", (width, height), 255)   # 255 = 保留，0 = 背景
    mask_pixels = mask.load()

    def matches(x: int, y: int) -> bool:
        r, g, b = pixels[x, y]
        dr, dg, db = r - bg[0], g - bg[1], b - bg[2]
        return dr * dr + dg * dg + db * db <= threshold

    # 从四边向内做扫描线漫水填充，只清理与边缘连通的背景，不破坏主体内部的近似色
    stack = [(x, 0) for x in range(width)]
    stack += [(x, height - 1) for x in range(width)]
    stack += [(0, y) for y in range(height)]
    stack += [(width - 1, y) for y in range(height)]
    while stack:
        x, y = stack.pop()
        if mask_pixels[x, y] == 0 or not matches(x, y):
            continue
        left = x
        while left > 0 and mask_pixels[left - 1, y] != 0 and matches(left - 1, y):
            left -= 1
        right = x
        while right < width - 1 and mask_pixels[right + 1, y] != 0 and matches(right + 1, y):
            right += 1
        for xx in range(left, right + 1):
            mask_pixels[xx, y] = 0
        for ny in (y - 1, y + 1):
            if 0 <= ny < height:
                xx = left
                while xx <= right:
                    if mask_pixels[xx, ny] != 0 and matches(xx, ny):
                        stack.append((xx, ny))
                        while xx <= right and mask_pixels[xx, ny] != 0 and matches(xx, ny):
                            xx += 1
                    xx += 1

    # 向内收 1 像素去掉背景色描边，再做轻微羽化
    mask = mask.filter(ImageFilter.MinFilter(3))
    if feather > 0:
        mask = mask.filter(ImageFilter.GaussianBlur(feather))

    bbox = mask.point(lambda v: 255 if v > 12 else 0).getbbox()
    if not bbox:
        return None
    out = image.convert("RGBA")
    out.putalpha(mask)
    out = out.crop(bbox)
    return _pad(out, 6)


def _pad(image: Image.Image, padding: int) -> Image.Image:
    out = Image.new("RGBA", (image.width + padding * 2, image.height + padding * 2), (0, 0, 0, 0))
    out.paste(image, (padding, padding), image)
    return out


def _card(image: Image.Image) -> Image.Image:
    """保留原图的圆角白边卡片，适合背景复杂、不适合抠图的照片。"""
    image = image.convert("RGBA")
    width, height = image.size
    pad = 20
    radius = max(14, int(min(width, height) * 0.08))
    canvas = Image.new("RGBA", (width + pad * 2, height + pad * 2), (0, 0, 0, 0))

    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        [pad + 1, pad + 5, pad + width + 1, pad + height + 5],
        radius=radius, fill=(140, 120, 95, 70),
    )
    canvas = Image.alpha_composite(canvas, shadow.filter(ImageFilter.GaussianBlur(7)))

    ImageDraw.Draw(canvas).rounded_rectangle(
        [pad, pad, pad + width, pad + height], radius=radius, fill=(255, 255, 255, 255),
    )
    mask = Image.new("L", (width, height), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, width - 1, height - 1], radius=max(6, radius - 6), fill=255,
    )
    canvas.paste(image, (pad, pad), mask)
    return canvas


def make_default_pet(size: int = 360) -> Image.Image:
    """首次运行时生成的奶油团子，保证程序开箱就有形象可看。"""
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    body = (int(size * 0.18), int(size * 0.30), int(size * 0.82), int(size * 0.88))
    ear_left = (int(size * 0.13), int(size * 0.14), int(size * 0.40), int(size * 0.44))
    ear_right = (int(size * 0.60), int(size * 0.14), int(size * 0.87), int(size * 0.44))
    cream = (248, 227, 199, 255)
    edge = (214, 184, 145, 255)
    pink = (245, 190, 180, 255)

    draw.ellipse(ear_left, fill=cream, outline=edge, width=3)
    draw.ellipse(ear_right, fill=cream, outline=edge, width=3)
    draw.ellipse((int(size * 0.20), int(size * 0.21), int(size * 0.33), int(size * 0.36)), fill=pink)
    draw.ellipse((int(size * 0.67), int(size * 0.21), int(size * 0.80), int(size * 0.36)), fill=pink)
    draw.ellipse(body, fill=cream, outline=edge, width=3)

    # 眼睛
    eye_y = int(size * 0.55)
    for cx in (int(size * 0.38), int(size * 0.62)):
        draw.ellipse((cx - int(size * 0.031), eye_y - int(size * 0.038),
                      cx + int(size * 0.031), eye_y + int(size * 0.038)),
                     fill=(74, 62, 50, 255))
        draw.ellipse((cx - int(size * 0.012), eye_y - int(size * 0.024),
                      cx + int(size * 0.004), eye_y - int(size * 0.010)),
                     fill=(255, 255, 255, 255))
    # 腮红
    blush = Image.new("RGBA", image.size, (0, 0, 0, 0))
    bd = ImageDraw.Draw(blush)
    for cx in (int(size * 0.27), int(size * 0.73)):
        bd.ellipse((cx - int(size * 0.055), int(size * 0.63),
                    cx + int(size * 0.055), int(size * 0.70)),
                   fill=(240, 160, 150, 110))
    image = Image.alpha_composite(image, blush.filter(ImageFilter.GaussianBlur(3)))

    # 嘴巴
    draw = ImageDraw.Draw(image)
    mouth_y = int(size * 0.66)
    draw.arc((int(size * 0.44), mouth_y - int(size * 0.03),
              int(size * 0.50), mouth_y + int(size * 0.03)), 20, 160, fill=(120, 95, 75, 255), width=3)
    draw.arc((int(size * 0.50), mouth_y - int(size * 0.03),
              int(size * 0.56), mouth_y + int(size * 0.03)), 20, 160, fill=(120, 95, 75, 255), width=3)
    # 小爪子
    for cx in (int(size * 0.34), int(size * 0.66)):
        draw.ellipse((cx - int(size * 0.06), int(size * 0.80),
                      cx + int(size * 0.06), int(size * 0.87)),
                     fill=cream, outline=edge, width=3)
    return image
