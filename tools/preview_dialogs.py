# -*- coding: utf-8 -*-
"""渲染两个设置对话框，检查布局。

只渲染，不动真实配置。
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

from core import AppConfig, ConfigManager, TaskConfig  # noqa: E402
from ui import theme as theme_mod  # noqa: E402
from ui.after_done import AfterDoneDialog  # noqa: E402
from ui.task_settings import TaskSettingsDialog  # noqa: E402

OUT = REPO / "docs" / "预览"


def load_fonts(app: QApplication) -> None:
    for p in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\msyhbd.ttc",
              r"C:\Windows\Fonts\STXINGKA.TTF"):
        QFontDatabase.addApplicationFont(p)
    for want in ("Microsoft YaHei", "微软雅黑"):
        if want in QFontDatabase.families():
            app.setFont(QFont(want, 9))
            break


def main() -> int:
    app = QApplication(sys.argv)
    load_fonts(app)
    theme = theme_mod.get("cyrene")
    app.setStyleSheet(theme_mod.stylesheet(theme))

    cfg_manager = ConfigManager(PROJECT / "config.json")
    try:
        cfg = cfg_manager.load()
    except Exception:
        cfg = AppConfig()

    # 任务设置：拿一个真实任务当样板，但不写回
    task = cfg.tasks[0] if cfg.tasks else TaskConfig()
    task_copy = TaskConfig.from_dict(task.to_dict(), 1)

    dlg1 = TaskSettingsDialog(task_copy, theme)
    dlg1.show()
    dlg2 = AfterDoneDialog(cfg, theme)
    dlg2.show()

    def shoot() -> None:
        OUT.mkdir(parents=True, exist_ok=True)
        for dlg, name in ((dlg1, "设置_任务.png"), (dlg2, "设置_跑完以后.png")):
            p = OUT / name
            ok = dlg.grab().save(str(p), "PNG")
            print(f"{'已保存' if ok else '失败'}: {p}  ({dlg.width()}x{dlg.height()})")
        app.quit()

    QTimer.singleShot(900, shoot)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
