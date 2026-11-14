# -*- coding: utf-8 -*-
"""离屏渲染启动界面并截图。只渲染，不启动任何游戏或脚本。"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

REPO = Path(__file__).resolve().parent.parent
PROJECT = REPO / "Anigame-script-manager"
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(PROJECT))

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtGui import QFont, QFontDatabase, QPainter, QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from ui.splash import Splash  # noqa: E402
from ui import theme as theme_mod  # noqa: E402

OUT = REPO / "docs" / "预览"

# 离屏渲染时 Qt 在 venv 里找不到字体目录，不显式加载就是一片方块。
# 行楷也要一起加载，否则启动界面那句台词会退回默认字体，看不出效果。
SYSTEM_FONTS = [
    r"C:\Windows\Fonts\msyh.ttc",      # 微软雅黑
    r"C:\Windows\Fonts\msyhbd.ttc",    # 微软雅黑粗体
    r"C:\Windows\Fonts\STXINGKA.TTF",  # 华文行楷（台词用的手写体）
]


def load_fonts(app: QApplication) -> None:
    for path in SYSTEM_FONTS:
        QFontDatabase.addApplicationFont(path)
    families = set(QFontDatabase.families())
    for want in ("Microsoft YaHei", "微软雅黑"):
        if want in families:
            app.setFont(QFont(want, 9))
            break
    for probe in ("STXingkai", "华文行楷"):
        print(f"行楷可用：{probe} -> {probe in families}")


def main() -> int:
    app = QApplication(sys.argv)
    load_fonts(app)

    theme = theme_mod.get("yukino")
    theme_key = "yukino"
    if len(sys.argv) > 1:
        theme_key = sys.argv[1]
        theme = theme_mod.get(theme_key)
    splash = Splash(theme)
    splash.resize(splash.width(), splash.height())
    splash.show()

    def run() -> None:
        OUT.mkdir(parents=True, exist_ok=True)
        # 有半透明背景，直接 grab() 拿到的就是界面真实观感
        pm = splash.grab()
        name = "启动界面.png" if theme_key == "yukino" else f"启动界面_{theme_key}.png"
        path = OUT / name
        ok = pm.save(str(path), "PNG")
        print(f"{'已保存' if ok else '保存失败'}: {path} ({pm.width()}x{pm.height()})")
        app.quit()

    QTimer.singleShot(600, run)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
