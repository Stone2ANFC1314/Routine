# -*- coding: utf-8 -*-
"""从星魂4 生成应用程序图标（多尺寸 .ico）。

为什么用星魂4：用户 2026-11-09 指定「app图标用星魂4」。
以前用的是 app.ico（另一个角色）或 ripples.ico（她眼睛的特写），
两者都不是想要的。

生成的 ico 带完整尺寸集（16/24/32/48/64/128/256），
Windows 会在任务栏、标题栏、资源管理器里按需要自动挑，
缺小尺寸的话系统会拿大图硬缩，边缘会糊。
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "assets" / "cyrene" / "原图" / "星魂4.png"
OUT = ROOT / "assets" / "cyrene" / "加工" / "app-icon.ico"

# Windows 图标需要的尺寸
SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]

# 取景：星魂4 的实际内容范围约 x 124–1912 / y 139–1958（2048×2048），
# 她的脸在中上部。取边长 0.8 倍内容短边的正方形，居中偏上一点。
CROP_RATIO = 0.80
CROP_CENTER_Y = 0.44          # 0 = 顶边，1 = 底边


def alpha_bbox(im: Image.Image) -> tuple[int, int, int, int]:
    """用 alpha 通道找真实内容范围。"""
    a = im.split()[-1]
    return a.getbbox() or (0, 0, im.width, im.height)


def main() -> int:
    if not SRC.exists():
        print(f"找不到源图：{SRC}")
        return 1

    im = Image.open(SRC).convert("RGBA")
    bx0, by0, bx1, by1 = alpha_bbox(im)
    cw, ch = bx1 - bx0, by1 - by0
    print(f"源图 {im.width}×{im.height}，内容 {cw}×{ch} @ ({bx0},{by0})")

    side = int(min(cw, ch) * CROP_RATIO)
    cx = bx0 + cw // 2
    cy = by0 + int(ch * CROP_CENTER_Y)
    left = max(0, min(cx - side // 2, im.width - side))
    top = max(0, min(cy - side // 2, im.height - side))
    print(f"取景 {side}×{side} @ ({left},{top})")

    square = im.crop((left, top, left + side, top + side))

    # 底色处理：星魂图是不规则形状，直接贴到纯色底上会露出方块状的
    # 深蓝背景（左上角和右侧那两块）。这里用「它自己放大模糊」当底，
    # 再把原图叠上去——边缘是同一张图的延展，看不出接缝。
    bg = square.resize((64, 64), Image.LANCZOS).resize(
        square.size, Image.LANCZOS
    )
    from PIL import ImageFilter

    bg = bg.filter(ImageFilter.GaussianBlur(radius=side * 0.04))
    base = Image.new("RGBA", square.size, (0, 0, 0, 255))
    base.alpha_composite(bg.convert("RGBA"))
    base.alpha_composite(square)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    base.save(OUT, format="ICO", sizes=SIZES)
    print(f"已生成：{OUT}  ({OUT.stat().st_size / 1024:.0f} KB)")

    # 顺便看一眼各尺寸下的样子
    preview_dir = ROOT / "docs" / "预览"
    preview_dir.mkdir(parents=True, exist_ok=True)
    strip = Image.new("RGB", (16 + 24 + 32 + 48 + 64 + 128 + 256 + 7 * 8, 256), (253, 247, 250))
    x = 8
    for size in (16, 24, 32, 48, 64, 128, 256):
        s = base.resize((size, size), Image.LANCZOS)
        strip.paste(s, (x, (256 - size) // 2), s if s.mode == "RGBA" else None)
        x += size + 8
    p = preview_dir / "图标_星魂4.png"
    strip.save(p)
    print(f"预览：{p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
