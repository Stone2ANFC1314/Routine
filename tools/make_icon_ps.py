# -*- coding: utf-8 -*-
"""用 PS 抠好的图生成应用图标。

和 make_icon.py 的区别
----------------------
make_icon.py 用的是带深蓝底的原始星魂图，靠「取景 + 模糊垫底」
硬凑出一个方形图标，角落的颜色终究不对。

这里用的星魂4PS.png 已经由用户手动抠掉背景（带真实 alpha），
所以不需要任何垫底技巧：把抠好的图居中放进正方形画布，
边缘之外保持透明（ico 支持透明），Windows 会正确渲染成「只有人像」。

抠好的好处
    - 任何深色/浅色任务栏背景下都干净
    - 不用模糊垫底，图标不会发灰
    - 缩小到 16px 也不会糊成一团
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "assets" / "cyrene" / "原图" / "星魂4PS.png"
OUT = ROOT / "assets" / "cyrene" / "加工" / "app-icon.ico"

SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]

# 抠好的图在正方形画布里占多少。
#
# 0.94 时内容几乎贴满画布，四周只剩 6% 的边距——缩小到 16px 会显得挤，
# 而且在任务栏里和别的图标并排时「块头」偏大。
# 参照用户给的 Sliver.ico（透明占比 55%，内容区四周留得多），
# 这里放宽到 0.82，留出约 18% 的空气。
FILL_RATIO = 0.82


def main() -> int:
    if not SRC.exists():
        print(f"找不到抠好的图：{SRC}")
        print("先放好 assets/cyrene/原图/星魂4PS.png，或用 tools/make_icon.py 的旧方案")
        return 1

    im = Image.open(SRC).convert("RGBA")
    bbox = im.split()[-1].getbbox()
    if not bbox:
        print("星魂4PS.png 全透明，没有可用内容")
        return 1
    art = im.crop(bbox)
    print(f"内容区 {art.width}×{art.height}")

    # 放进正方形画布：按长边缩放，居中
    canvas_side = int(max(art.width, art.height) / FILL_RATIO)
    canvas = Image.new("RGBA", (canvas_side, canvas_side), (0, 0, 0, 0))
    canvas.alpha_composite(
        art,
        ((canvas_side - art.width) // 2, (canvas_side - art.height) // 2),
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(OUT, format="ICO", sizes=SIZES)
    print(f"已生成：{OUT}  ({OUT.stat().st_size / 1024:.0f} KB)")

    # 各尺寸预览：放在深、浅两种任务栏底色上
    preview_dir = ROOT / "docs" / "预览"
    preview_dir.mkdir(parents=True, exist_ok=True)
    sizes = [16, 24, 32, 48, 64, 128, 256]
    gap = 10
    total_w = sum(sizes) + gap * (len(sizes) + 1)
    strip = Image.new("RGB", (total_w, 128 * 2 + 30), (245, 245, 245))
    for row, bg in enumerate(((32, 32, 40, 255), (250, 250, 252, 255))):
        x = gap
        for s in sizes:
            icon = canvas.resize((s, s), Image.LANCZOS)
            cell = Image.new("RGBA", (s + 4, s + 4), bg)
            cell.alpha_composite(icon, (2, 2))
            strip.paste(cell.convert("RGB"), (x, 10 + row * (128 + 10)))
            x += s + gap
    p = preview_dir / "图标_PS版.png"
    strip.save(p)
    print(f"预览：{p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
