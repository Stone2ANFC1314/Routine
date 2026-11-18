# -*- coding: utf-8 -*-
"""离屏渲染主界面并截图，用于检查改动后的样子。

只渲染，不启动任何游戏或脚本。

字体处理
--------
必须走 ui.fonts.ensure_fonts()——和 main.py 完全一样的路径。
不要只做 QFontDatabase.addApplicationFont：那样虽然能加载，
但和真实运行时不一致，截图里行楷可能退化成黑体，看不出实际效果。

（Qt 在 venv 里枚举不到系统字体，families() 返回空列表，
所以必须主动注册 STXINGKA.TTF。这个坑踩过好几次。）
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

from ui.fonts import ensure_fonts  # noqa: E402
from ui.main_window_new import MainWindow  # noqa: E402

OUT = REPO / "docs" / "预览"

# 正文字体（微软雅黑）。行楷由 ensure_fonts() 负责。
BODY_FONTS = [
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\msyhbd.ttc",
]


def prepare_fonts(app: QApplication) -> None:
    """和 main.py 一样：先 ensure_fonts，再设正文字体。"""
    for path in BODY_FONTS:
        if QFontDatabase.addApplicationFont(path) < 0:
            print(f"字体加载失败：{path}")

    family = ensure_fonts()
    print(f"手写字体：{family or '没找到，会退回黑体'}")

    families = set(QFontDatabase.families())
    for want in ("Microsoft YaHei", "微软雅黑"):
        if want in families:
            app.setFont(QFont(want, 9))
            print(f"正文字体：{want}")
            break


def shoot(name: str, win: MainWindow) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    ok = win.grab().save(str(path), "PNG")
    print(f"{'已保存' if ok else '保存失败'}: {path}  ({win.width()}x{win.height()})")


def main() -> int:
    app = QApplication(sys.argv)
    prepare_fonts(app)

    win = MainWindow()
    win.resize(1180, 760)
    win.show()

    # 文件名带时间戳，避免缓存挡住新图
    from datetime import datetime

    stamp = datetime.now().strftime("%m%d_%H%M%S")

    def run() -> None:
        shoot(f"主界面_{stamp}.png", win)
        app.quit()

    QTimer.singleShot(2500, run)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
