# -*- coding: utf-8 -*-
"""从打包好的 exe 环境里渲染一次主界面，验证资源路径是否正确。

原理：用 PyInstaller 的目录版产物，把本脚本当作「测试入口」跑不起来
（exe 已经编译死了入口）。所以改为：直接在 dist 的 _internal 目录下
用打包进去的资源 + 源码里的 UI 代码渲染，验证 asset() 解析出的路径。

这不是完美的验证（真正的 exe 是编译过的），但能确认
「资源在 _internal 下能不能被找到」这个最关键的点。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

REPO = Path(__file__).resolve().parent.parent
DIST = REPO / "dist" / "游戏日常" / "_internal"
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "Anigame-script-manager"))

# 模拟打包后的资源根目录
import ui.paths as P  # noqa: E402

P.resource_dir = lambda: DIST          # type: ignore[assignment]
P._meipass = lambda: DIST              # type: ignore[assignment]

from PySide6.QtGui import QFontDatabase  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from ui.main_window_new import MainWindow  # noqa: E402

OUT = REPO / "docs" / "预览"


def main() -> int:
    app = QApplication(sys.argv)
    for p in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\STXINGKA.TTF"):
        QFontDatabase.addApplicationFont(p)

    # 确认每个资源都能在 dist 里找到
    from ui.paths import asset

    checks = [
        ("cyrene", "原图", "art-reading.png"),
        ("cyrene", "原图", "art-starry.jpg"),
        ("cyrene", "原图", "星魂1.png"),
        ("cyrene", "原图", "星魂3.png"),
        ("cyrene", "原图", "星魂4.png"),
        ("cyrene", "加工", "logo-trim.png"),
        ("cyrene", "加工", "signature.png"),
    ]
    missing = []
    for parts in checks:
        p = asset(*parts)
        ok = p.exists()
        print(f"{'✓' if ok else '✗'} {p.relative_to(DIST) if ok else p}")
        if not ok:
            missing.append(parts)
    if missing:
        print(f"\n缺少 {len(missing)} 个资源，exe 里会显示空白")
        return 1

    print("\n全部资源都在。开始渲染主界面…")
    win = MainWindow()
    win.resize(1180, 760)
    win.show()

    from PySide6.QtCore import QTimer

    def shoot() -> None:
        OUT.mkdir(parents=True, exist_ok=True)
        path = OUT / "exe_验证_主界面.png"
        ok = win.grab().save(str(path), "PNG")
        print(f"{'已保存' if ok else '失败'}: {path}")
        app.quit()

    QTimer.singleShot(2500, shoot)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
