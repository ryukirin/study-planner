"""生成计划本图标：靛蓝超椭圆底板上一张白色日历卡片，带挂环和渐变对勾。

输出：
- assets/app_icon.png：512 px，大图
- assets/app_icon.ico：16 到 256 px 多尺寸，exe 和窗口图标
- assets/tray_icon.png：64 px，托盘图标，使用小尺寸版本的粗线条
- web/logo.png：96 px，界面侧栏左上角

32 px 及以下使用小尺寸版本：卡片更大、挂环和对勾更粗，没有投影，保证托盘和标题栏里看得清。
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

BRAND = [(0.0, (128, 120, 255)), (0.55, (92, 84, 234)), (1.0, (60, 50, 192))]
CHECK = [(0.0, (99, 102, 241)), (1.0, (130, 70, 236))]
RING = [(0.0, (70, 62, 190)), (1.0, (45, 36, 150))]
CARD = [(0.0, (255, 255, 255)), (1.0, (233, 234, 252))]
ICO_SIZES = [16, 20, 24, 32, 40, 48, 64, 128, 256]


# ---------- 绘图工具 ----------

def lerp(t: np.ndarray, stops) -> np.ndarray:
    t = np.clip(t, 0, 1)
    out = np.zeros(t.shape + (3,))
    for (p0, c0), (p1, c1) in zip(stops, stops[1:]):
        m = (t >= p0) & (t <= p1)
        local = ((t - p0) / (p1 - p0))[m][:, None]
        out[m] = np.array(c0) + (np.array(c1) - np.array(c0)) * local
    return out


def linear(S: int, stops, angle: float) -> Image.Image:
    y, x = np.mgrid[0:S, 0:S] / (S - 1)
    a = math.radians(angle)
    t = x * math.cos(a) + y * math.sin(a)
    t = (t - t.min()) / (t.max() - t.min())
    rgb = lerp(t, stops)
    return Image.fromarray(np.dstack([rgb, np.full((S, S), 255)]).astype(np.uint8), "RGBA")


def squircle(S: int, box, n: float = 4.6) -> Image.Image:
    x0, y0, x1, y1 = [v * S for v in box]
    y, x = np.mgrid[0:S, 0:S] + 0.5
    cx, cy, rx, ry = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2
    v = np.abs((x - cx) / rx) ** n + np.abs((y - cy) / ry) ** n
    return Image.fromarray(((v <= 1) * 255).astype(np.uint8), "L")


def new_mask(S: int):
    mask = Image.new("L", (S, S), 0)
    return mask, ImageDraw.Draw(mask)


def paint(source: Image.Image, mask: Image.Image, opacity: float = 1.0) -> Image.Image:
    layer = source.copy()
    alpha = ImageChops.multiply(layer.getchannel("A"), mask)
    if opacity < 1:
        alpha = alpha.point(lambda v: int(v * opacity))
    layer.putalpha(alpha)
    return layer


def solid(S: int, color) -> Image.Image:
    return Image.new("RGBA", (S, S), tuple(color) + (255,))


def shadow(mask: Image.Image, S: int, dy: float, blur: float, color, opacity: float) -> Image.Image:
    layer = solid(S, color)
    layer.putalpha(mask.point(lambda v: int(v * opacity)))
    layer = layer.filter(ImageFilter.GaussianBlur(blur))
    out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    out.paste(layer, (0, int(dy)), layer)
    return out


def stroke(draw: ImageDraw.ImageDraw, points, width: float) -> None:
    """带圆头的折线。"""
    draw.line(points, fill=255, width=int(width), joint="curve")
    r = width / 2
    for x, y in (points[0], points[-1]):
        draw.ellipse((x - r, y - r, x + r, y + r), fill=255)


# ---------- 图标 ----------

def draw_icon(S: int, small: bool) -> Image.Image:
    """在 S×S 画布上画图标。small 为 True 时使用小尺寸版本。"""
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))

    # 底板：超椭圆 + 对角渐变 + 顶部高光 + 底部暗边
    box = (0.03, 0.03, 0.97, 0.97) if small else (0.07, 0.07, 0.93, 0.93)
    plate = squircle(S, box)
    if not small:
        img = Image.alpha_composite(img, shadow(plate, S, 0.018 * S, 0.025 * S, (20, 16, 60), 0.28))
    img = Image.alpha_composite(img, paint(linear(S, BRAND, 62), plate))
    rows = np.mgrid[0:S, 0:S][0] / S
    gloss = np.clip((0.55 - rows) / 0.5, 0, 1) * 255 * 0.22
    img = Image.alpha_composite(img, paint(Image.fromarray(np.dstack([np.full((S, S, 3), 255), gloss]).astype(np.uint8), "RGBA"), plate))
    if not small:
        inner = squircle(S, (box[0] + 0.006, box[1] + 0.006, box[2] - 0.006, box[3] - 0.012))
        img = Image.alpha_composite(img, paint(solid(S, (40, 30, 140)), ImageChops.subtract(plate, inner), 0.35))

    # 日历卡片
    card_box = (0.19, 0.27, 0.81, 0.85) if small else (0.235, 0.29, 0.765, 0.79)
    card, draw = new_mask(S)
    draw.rounded_rectangle([v * S for v in card_box], radius=(0.10 if small else 0.085) * S, fill=255)
    if not small:
        img = Image.alpha_composite(img, shadow(card, S, 0.03 * S, 0.035 * S, (25, 15, 90), 0.45))
    img = Image.alpha_composite(img, paint(linear(S, CARD, 90), card))
    if not small:
        head, draw = new_mask(S)
        draw.rectangle((0, card_box[1] * S, S, (card_box[1] + 0.12) * S), fill=255)
        img = Image.alpha_composite(img, paint(solid(S, (226, 228, 255)), ImageChops.multiply(head, card)))

    # 挂环
    rings, draw = new_mask(S)
    width = (0.085 if small else 0.052) * S
    top, bottom = (0.15, 0.36) if small else (0.225, 0.345)
    for cx in (0.38, 0.62):
        stroke(draw, [(cx * S, top * S + width / 2), (cx * S, bottom * S - width / 2)], width)
    img = Image.alpha_composite(img, paint(linear(S, RING, 90), rings))

    # 对勾
    check, draw = new_mask(S)
    if small:
        stroke(draw, [(0.34 * S, 0.58 * S), (0.465 * S, 0.705 * S), (0.67 * S, 0.47 * S)], 0.115 * S)
    else:
        stroke(draw, [(0.375 * S, 0.59 * S), (0.465 * S, 0.68 * S), (0.635 * S, 0.505 * S)], 0.068 * S)
    return Image.alpha_composite(img, paint(linear(S, CHECK, 45), check))


def render(size: int, small: bool | None = None) -> Image.Image:
    """按目标尺寸超采样绘制后缩小。"""
    if small is None:
        small = size <= 32
    scale = 4 if size >= 256 else 16
    return draw_icon(size * scale, small).resize((size, size), Image.LANCZOS)


def main() -> None:
    root = Path(__file__).resolve().parent
    assets = root / "assets"
    assets.mkdir(exist_ok=True)

    render(512).save(assets / "app_icon.png")
    frames = [render(size) for size in ICO_SIZES]
    frames[-1].save(assets / "app_icon.ico", format="ICO", sizes=[(s, s) for s in ICO_SIZES], append_images=frames[:-1])
    render(64, small=True).save(assets / "tray_icon.png")
    render(96).save(root / "web" / "logo.png")
    for path in ("assets/app_icon.png", "assets/app_icon.ico", "assets/tray_icon.png", "web/logo.png"):
        print(root / path)


if __name__ == "__main__":
    main()
