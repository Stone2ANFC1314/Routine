# -*- coding: utf-8 -*-
"""用情人节那张抠好的图生成应用图标。

和 make_icon_ps.py 的区别：那张（星魂4）内容集中在中上部，直接居中即可；
情人节这张是半身构图，带手势和蝴蝶结，整张塞进方形图标会显得小。
所以这里多试几种取景，输出对比图让人挑。

取景思路
    内容区正好是 1000×1000（抠图时保留了原画布），
    但人物实际占的范围和视觉重心需要看比例决定裁多少。
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "assets" / "cyrene" / "原图" / "2026.2.14情人节昔涟PS.png"
OUT_DIR = ROOT / "assets" / "cyrene" / "加工"
PREVIEW = ROOT / "docs" / "预览"

SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def build(im: Image.Image, fill: float, cy: float) -> Image.Image:
    """按「内容占画布多少、纵向重心在哪」拼出方形画布。"""
    bbox = im.split()[-1].getbbox()
    art = im.crop(bbox) if bbox else im
    side = int(max(art.width, art.height) / fill)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    ox = (side - art.width) // 2
    oy = int((side - art.height) * cy)
    canvas.alpha_composite(art, (ox, oy))
    return canvas


def contact_sheet(variants: list[tuple[str, Image.Image]]) -> Path:
    """把几种取景排成一行对比，每种都带 256 和 32 两个尺寸。"""
    gap = 14
    cells = []
    for tag, canvas in variants:
        big = canvas.resize((200, 200), Image.LANCZOS)
        small = canvas.resize((32, 32), Image.LANCZOS)
        cells.append((tag, big, small))

    W = gap + sum(200 + gap * 2 for _ in cells)
    H = 200 + 70
    sheet = Image.new("RGB", (W, H), (30, 26, 36))
    x = gap
    for tag, big, small in cells:
        cell = Image.new("RGBA", (200, 200), (32, 32, 40, 255))
        cell.alpha_composite(big)
        sheet.paste(cell.convert("RGB"), (x, 20))
        cell2 = Image.new("RGBA", (36, 36), (32, 32, 40, 255))
        cell2.alpha_composite(small, (2, 2))
        sheet.paste(cell2.convert("RGB"), (x + 84, 20 + 200 + 8))
        x += 200 + gap * 2
    PREVIEW.mkdir(parents=True, exist_ok=True)
    p = PREVIEW / "图标_情人节_取景.png"
    sheet.save(p)
    return p


def main() -> int:
    if not SRC.exists():
        print(f"找不到：{SRC}")
        return 1
    im = Image.open(SRC).convert("RGBA")

    # 三种取景：贴满 / 标准留白 / 偏上（让脸更突出）
    variants = [
        ("贴满 0.98", build(im, 0.98, 0.0)),
        ("留白 0.82", build(im, 0.82, 0.5)),
        ("偏上 0.82", build(im, 0.82, 0.0)),
    ]

    p = contact_sheet(variants)
    print(f"对比图：{p}")

    # 先按「留白 0.82 + 垂直居中」生成一版，方便立刻看效果；
    # 定了取景再改 FILL / CY 重新生成。
    chosen = variants[1][1]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    dst = OUT_DIR / "app-icon.ico"
    chosen.save(dst, format="ICO", sizes=SIZES)
    print(f"已生成：{dst}  ({dst.stat().st_size / 1024:.0f} KB)")

    # 各尺寸在深色任务栏上的样子
    sizes = [16, 24, 32, 48, 64, 128, 256]
    total_w = sum(sizes) + 10 * (len(sizes) + 1)
    strip = Image.new("RGB", (total_w, 290), (245, 245, 245))
    for row, bg in enumerate(((32, 32, 40, 255), (250, 250, 252, 255))):
        x = 10
        for s in sizes:
            icon = chosen.resize((s, s), Image.LANCZOS)
            cell = Image.new("RGBA", (s + 4, s + 4), bg)
            cell.alpha_composite(icon, (2, 2))
            strip.paste(cell.convert("RGB"), (x, 10 + row * 140))
            x += s + 10
    p2 = PREVIEW / "图标_情人节.png"
    strip.save(p2)
    print(f"尺寸预览：{p2}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
