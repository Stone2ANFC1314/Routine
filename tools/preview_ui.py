# -*- coding: utf-8 -*-
"""离屏渲染主界面并截图，用于检查改动后的样子。

只渲染，不启动任何游戏或脚本。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

REPO = Path(__file__).resolve().parent.parent      # Routine
PROJECT = REPO / "Anigame-script-manager"          # 主程序目录
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(PROJECT))

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtGui import QFont, QFontDatabase  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from ui.main_window_new import MainWindow  # noqa: E402

OUT = REPO / "docs" / "预览"

# 离屏渲染时 Qt 在 venv 里找不到字体目录，中文会全变成方块。
# 显式从系统 fonts 目录加载。行楷也要——标题栏那句台词是行楷，
# 不加载就退回黑体，截图里看不出「手写」的效果。
SYSTEM_FONTS = [
    r"C:\Windows\Fonts\msyh.ttc",      # 微软雅黑
    r"C:\Windows\Fonts\msyhbd.ttc",    # 微软雅黑粗体
    r"C:\Windows\Fonts\STXINGKA.TTF",  # 华文行楷（台词）
]


def load_fonts(app: QApplication) -> None:
    for path in SYSTEM_FONTS:
        fid = QFontDatabase.addApplicationFont(path)
        if fid < 0:
            print(f"字体加载失败：{path}")
    families = set(QFontDatabase.families())
    for want in ("Microsoft YaHei", "微软雅黑"):
        if want in families:
            app.setFont(QFont(want, 9))
            print(f"使用字体：{want}")
            break
    print(f"行楷可用：{'STXingkai' in families}")


def shoot(name: str, win: MainWindow) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    ok = win.grab().save(str(path), "PNG")
    print(f"{'已保存' if ok else '保存失败'}: {path}  ({win.width()}x{win.height()})")


def main() -> int:
    app = QApplication(sys.argv)
    load_fonts(app)
    win = MainWindow()
    win.resize(1180, 760)
    win.show()

    def run() -> None:
        shoot("自动化_超时可编辑.png", win)
        app.quit()

    QTimer.singleShot(700, run)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
