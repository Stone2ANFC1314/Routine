# -*- coding: utf-8 -*-
"""Ripples · 涟漪 入口。

源码运行与 PyInstaller 打包成 exe 用的是同一个入口。
两者的区别由 ui.paths 统一处理，这里只负责把 sys.path 补齐。
"""
from __future__ import annotations

import sys
from pathlib import Path

# 打包后（sys.frozen）模块都在 exe 里，PyInstaller 已经处理好了 sys.path；
# 源码运行时要把 Anigame-script-manager/ 和项目根都加进来，
# 否则 `import core` 和 `import status` 都会失败。
if not getattr(sys, "frozen", False):
    _HERE = Path(__file__).resolve().parent          # Anigame-script-manager
    _ROOT = _HERE.parent                             # 项目根
    for _p in (str(_ROOT), str(_HERE)):
        if _p not in sys.path:
            sys.path.insert(0, _p)

from core import _write_startup_error

try:
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    from ui.main_window_new import MainWindow
except Exception as exc:
    _write_startup_error(exc)
    print("启动失败，错误已写入 startup_error.log：", exc)
    raise


def main() -> int:
    app = QApplication(sys.argv)

    # 必须在建窗口之前把行楷注册好。
    # QSS 里的 font-family 是在控件创建时解析的，晚一步就解析不到，
    # 那句台词会静默变成黑体——而且不会报错，只会「看起来不对」。
    try:
        from ui.fonts import ensure_fonts

        family = ensure_fonts()
        if family:
            print(f"手写字体：{family}")
        else:
            print("没找到华文行楷，台词会退回楷体或黑体")
    except Exception as exc:
        print(f"字体加载失败（不影响启动）：{exc}")

    window = MainWindow()

    # 启动画面：先亮一小会儿，再交给主窗口。
    # 时长压得很短（900ms）—— 它只是让「打开」这件事有个开始的感觉，
    # 不该真的让人等。主窗口在下面已经开始构造，所以这段几乎是白送的。
    splash = None
    try:
        from ui.splash import Splash

        splash = Splash(window.theme)
        splash.show()

        def _handoff() -> None:
            window.show()
            if splash is not None:
                splash.close()

        # 保证启动画面至少完整露出一次，同时主窗口已经准备好了
        QTimer.singleShot(900, _handoff)
    except Exception:
        # 启动画面出任何问题都不该挡住主程序
        window.show()

    return app.exec()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        _write_startup_error(exc)
        print("程序异常退出，错误已写入 startup_error.log：", exc)
        raise
