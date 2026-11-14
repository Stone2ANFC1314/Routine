# -*- coding: utf-8 -*-
"""把候选字体渲染成同一句话的对比图。

只做字体制样对比，不改动程序。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

REPO = Path(__file__).resolve().parent.parent
PROJECT = REPO / "Anigame-script-manager"
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(PROJECT))

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import (  # noqa: E402
    QColor,
    QFont,
    QFontDatabase,
    QFontMetrics,
    QPainter,
    QPixmap,
)
from PySide6.QtWidgets import QApplication  # noqa: E402

OUT = REPO / "docs" / "预览"
CAND_DIR = REPO / "assets" / "fonts" / "_candidates"

LINE1 = "就算世界并不温柔，那也没有关系。"
LINE2 = "只要我不曾忘记，就永远有人记得「笑容」的意义。"
BRAND = "涟漪"

BG = QColor("#FDF7FA")
TEXT = QColor("#4A3640")
DIM = QColor(74, 54, 64, 200)
ACCENT = QColor("#DF7BA0")

# (显示名, 字体文件或 None 表示系统字体, 家族名, 说明)
CANDIDATES = [
    ("华文行楷（现在的）", None, "STXingkai", "系统自带，用户没装就退回黑体"),
    ("霞鹜文楷 Lite", CAND_DIR / "LXGWWenKaiLite-Regular.ttf", "LXGW WenKai Lite", "OFL，清秀楷体"),
    ("马善政毛笔楷书", CAND_DIR / "MaShanZheng-Regular.ttf", "Ma Shan Zheng", "OFL，笔锋明显"),
    ("志莽行书", CAND_DIR / "ZhiMangXing-Regular.ttf", "Zhi Mang Xing", "OFL，行书连笔"),
    ("龙藏体", CAND_DIR / "LongCang-Regular.ttf", "Long Cang", "OFL，细笔草意"),
]

W, H = 1200, 250


def draw_card(painter: QPainter, y: int, name: str, family: str, note: str) -> None:
    painter.setPen(QColor("#C9A9B8"))
    painter.drawLine(60, y - 18, W - 60, y - 18)

    f_label = QFont("Microsoft YaHei", 10)
    f_label.setBold(True)
    painter.setFont(f_label)
    painter.setPen(ACCENT)
    painter.drawText(60, y + 4, f"{name}   ({note})")

    f1 = QFont(family, 17)
    painter.setFont(f1)
    painter.setPen(TEXT)
    painter.drawText(60, y + 46, LINE1)

    f2 = QFont(family, 14)
    painter.setFont(f2)
    painter.setPen(DIM)
    painter.drawText(60, y + 84, LINE2)

    f3 = QFont(family, 22)
    f3.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 4)
    painter.setFont(f3)
    painter.setPen(ACCENT)
    painter.drawText(W - 220, y + 60, BRAND)


def main() -> int:
    app = QApplication(sys.argv)

    # 基准正文字体
    for p in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\STXINGKA.TTF"):
        QFontDatabase.addApplicationFont(p)

    loaded = {}
    for name, path, family, note in CANDIDATES:
        if path is not None and path.exists():
            fid = QFontDatabase.addApplicationFont(str(path))
            fams = QFontDatabase.applicationFontFamilies(fid) if fid >= 0 else []
            loaded[name] = (fams[0] if fams else family, note)
            print(f"{name}: addApplicationFont={fid} family={fams}")
        else:
            have = family in QFontDatabase.families()
            loaded[name] = (family, note)
            print(f"{name}: 系统字体可用={have}")

    rows = [(n, loaded[n][0], loaded[n][1]) for n, _, _, _ in CANDIDATES
            if (CANDIDATES[[c[0] for c in CANDIDATES].index(n)][1] is None)
            or CANDIDATES[[c[0] for c in CANDIDATES].index(n)][1].exists()]
    height = 60 + len(rows) * H
    pm = QPixmap(W, height)
    pm.fill(BG)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

    f_title = QFont("Microsoft YaHei", 13)
    f_title.setBold(True)
    p.setFont(f_title)
    p.setPen(TEXT)
    p.drawText(60, 34, "标题栏那句台词 × 字体候选")

    y = 80
    for name, family, note in rows:
        draw_card(p, y, name, family, note)
        y += H

    p.end()
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / "字体候选.png"
    pm.save(str(out), "PNG")
    print(f"已保存：{out} ({pm.width()}x{pm.height()})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
