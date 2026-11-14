# -*- coding: utf-8 -*-
"""从「原图」生成程序实际使用的派生素材。

仓库里不带任何美术图（版权原因）。想用完整的昔涟主题，
需要自己准备原图，然后跑这个脚本生成派生文件。

用法
----
1. 把这些图放进 `assets/cyrene/原图/`：
       art-reading.png     深色房间看书那张（整窗壁纸，16:9 最好）
       art-starry.jpg      星空回眸（启动界面的壁纸，16:9）
       星魂1.png            侧后身影（标题栏右侧装饰）
       星魂3.png            手持光锥（已不再使用，可省）
       星魂4.png            笑脸特写（应用图标、标题栏图标）
       logo-official.png   官方手写 logo（带大量透明留白）

2. 运行：
       python tools/prepare_assets.py

3. 会在 `assets/cyrene/加工/` 下生成：
       logo-trim.png       裁掉透明留白的 logo
       app-icon.ico        多尺寸应用图标（星魂4）
       p-side.png          侧栏装饰用的缩图

缺哪张就跳过哪步，不会报错——程序会自己判断哪些素材可用。
"""
from __future__ import annotations

from pathlib import Path

try:
    from PIL import Image
except ImportError:
    raise SystemExit(
        "需要 Pillow：\n"
        "    .venv\\Scripts\\python.exe -m pip install pillow\n"
        "（或用装了 Pillow 的解释器跑，比如 Anaconda）"
    )

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "assets" / "cyrene" / "原图"
OUT = ROOT / "assets" / "cyrene" / "加工"

ICON_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def log(ok: bool, msg: str) -> None:
    # 只用 GBK 能编码的符号：cmd 默认代码页 936，
    # U+2713（✓）会让 print 直接抛 UnicodeEncodeError。
    # 这个坑写在交接文档第 9 条里，这里自己又踩了一次。
    print(f"{'√' if ok else '·'} {msg}")


def trim_logo() -> None:
    """裁掉 logo-official.png 四周的透明留白。

    原图 335×303，实际笔画只有 254×150 那一块。按整张图画的话，
    界面上的 logo 会比设定的尺寸小一圈，而且位置看着发飘。
    """
    src = SRC / "logo-official.png"
    if not src.exists():
        log(False, "logo-official.png 不存在，跳过 logo 裁切")
        return
    im = Image.open(src).convert("RGBA")
    bbox = im.split()[-1].getbbox()
    if not bbox:
        log(False, "logo-official.png 全透明，跳过")
        return
    trimmed = im.crop(bbox)
    OUT.mkdir(parents=True, exist_ok=True)
    dst = OUT / "logo-trim.png"
    trimmed.save(dst)
    log(True, f"logo-trim.png  {trimmed.width}×{trimmed.height}")


def make_icon() -> None:
    """从星魂4 生成应用图标（多尺寸 .ico）。"""
    src = SRC / "星魂4.png"
    if not src.exists():
        log(False, "星魂4.png 不存在，跳过图标生成")
        return
    im = Image.open(src).convert("RGBA")
    bbox = im.split()[-1].getbbox() or (0, 0, im.width, im.height)
    bx0, by0, bx1, by1 = bbox
    cw, ch = bx1 - bx0, by1 - by0

    # 取内容包围盒的 0.8 倍边长，中心偏上一点（她的脸在中上部）
    side = int(min(cw, ch) * 0.80)
    cx = bx0 + cw // 2
    cy = by0 + int(ch * 0.44)
    left = max(0, min(cx - side // 2, im.width - side))
    top = max(0, min(cy - side // 2, im.height - side))
    square = im.crop((left, top, left + side, top + side))

    # 用自己放大模糊当底，避免不规则形状露出深色背景块
    from PIL import ImageFilter

    bg = square.resize((64, 64), Image.LANCZOS).resize(square.size, Image.LANCZOS)
    bg = bg.filter(ImageFilter.GaussianBlur(radius=side * 0.04))
    base = Image.new("RGBA", square.size, (0, 0, 0, 255))
    base.alpha_composite(bg.convert("RGBA"))
    base.alpha_composite(square)

    OUT.mkdir(parents=True, exist_ok=True)
    dst = OUT / "app-icon.ico"
    base.save(dst, format="ICO", sizes=ICON_SIZES)
    log(True, f"app-icon.ico  {dst.stat().st_size // 1024} KB")


def make_side() -> None:
    """侧栏装饰用的缩图。

    原图 2048×2048、3MB，每次启动都读全尺寸太浪费。
    缩到 560 宽足够侧栏那个位置用了。
    """
    src = SRC / "星魂3.png"
    if not src.exists():
        log(False, "星魂3.png 不存在，跳过侧栏缩图")
        return
    im = Image.open(src).convert("RGBA")
    if im.width > 560:
        ratio = 560 / im.width
        im = im.resize((560, int(im.height * ratio)), Image.LANCZOS)
    OUT.mkdir(parents=True, exist_ok=True)
    dst = OUT / "p-side.png"
    im.save(dst)
    log(True, f"p-side.png  {im.width}×{im.height}")


def main() -> int:
    if not SRC.exists():
        print(f"先把原图放进：{SRC}")
        print("需要的文件：art-reading.png, art-starry.jpg, 星魂1.png,")
        print("            星魂3.png, 星魂4.png, logo-official.png")
        return 1

    print(f"原图目录：{SRC}")
    print(f"输出目录：{OUT}\n")

    trim_logo()
    make_icon()
    make_side()

    print("\n完成。缺的图不影响启动——程序会自动用「简约」主题。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
