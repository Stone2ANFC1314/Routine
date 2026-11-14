# -*- coding: utf-8 -*-
"""渲染主界面，并等状态数据真正加载完再截图。

preview_ui.py 是 700ms 就截，本机状态接口要几秒，
所以左栏永远是「读取中…」。这个脚本等够再截。
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

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtGui import QFont, QFontDatabase  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from ui.main_window_new import MainWindow  # noqa: E402

OUT = REPO / "docs" / "预览"
SYSTEM_FONTS = [
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\msyhbd.ttc",
    r"C:\Windows\Fonts\STXINGKA.TTF",
]

WAIT_MS = int(os.environ.get("PREVIEW_WAIT_MS", "25000"))


def load_fonts(app: QApplication) -> None:
    for path in SYSTEM_FONTS:
        QFontDatabase.addApplicationFont(path)
    for want in ("Microsoft YaHei", "微软雅黑"):
        if want in QFontDatabase.families():
            app.setFont(QFont(want, 9))
            break


def main() -> int:
    app = QApplication(sys.argv)
    load_fonts(app)

    win = MainWindow()
    win.resize(1180, 760)
    win.show()

    def run() -> None:
        OUT.mkdir(parents=True, exist_ok=True)
        name = os.environ.get("PREVIEW_NAME", "主界面_含状态.png")
        path = OUT / name
        ok = win.grab().save(str(path), "PNG")
        print(f"{'已保存' if ok else '保存失败'}: {path}")
        app.quit()

    print(f"等待 {WAIT_MS} ms 让状态加载…")
    QTimer.singleShot(WAIT_MS, run)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
