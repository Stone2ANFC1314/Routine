# -*- coding: utf-8 -*-
"""验证拖动排序：模拟鼠标拖动，检查行是否实时换位、顺序是否写回配置。"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, r"A:\Desktop\Work\Routine")
sys.path.insert(0, r"A:\Desktop\Work\Routine\Anigame-script-manager")

from PySide6.QtCore import QPoint, QPointF, Qt, QTimer
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication

from ui.main_window_new import MainWindow, TaskRow

app = QApplication([])
QFontDatabase.addApplicationFont(r"C:\Windows\Fonts\msyh.ttc")

win = MainWindow()
win.resize(1180, 760)
win.show()


def names_in_layout() -> list[str]:
    """按布局顺序读出任务名。"""
    lay = win.queue_layout
    out = []
    for i in range(lay.count()):
        item = lay.itemAt(i)
        w = item.widget() if item is not None else None
        if isinstance(w, TaskRow):
            out.append(w.findChild(type(w._idx_label)).__class__ and w)
    return out


def dump(tag: str) -> None:
    lay = win.queue_layout
    rows = [lay.itemAt(i).widget() for i in range(lay.count())]
    rows = [r for r in rows if isinstance(r, TaskRow)]
    print(f"\n[{tag}]")
    for pos, r in enumerate(rows, 1):
        # 行里第一个 TaskName 标签的文字
        lbls = [c for c in r.findChildren(type(r._idx_label)) if c.objectName() == "TaskName"]
        name = lbls[0].text() if lbls else "?"
        print(f"  槽位{pos}: {name}")


def run() -> None:
    dump("初始")

    lay = win.queue_layout
    rows = [lay.itemAt(i).widget() for i in range(lay.count())]
    rows = [r for r in rows if isinstance(r, TaskRow)]
    if len(rows) < 3:
        print("行数不足，退出")
        app.quit()
        return

    # 把第 1 行往下拖到第 3 行的位置
    src = rows[0]
    target = rows[2]
    tgt_geo = target.geometry()
    src_h = src.sizeHint().height()

    print(f"\n拖动：{src._index} 号行 → 第 3 行所在位置")
    print(f"  第3行 geometry: top={tgt_geo.top()} bottom={tgt_geo.bottom()}")

    # 模拟：直接调用 _drag_to，传一个落在第 3 行范围的全局坐标
    parent = src.parentWidget()
    local_pt = QPoint(10, tgt_geo.center().y())
    global_pt = QPointF(parent.mapToGlobal(local_pt))
    src._drag_to(global_pt)
    dump("拖动到第3行后")

    # 松手：触发 move_task
    win.move_task(src._index, src._index)
    dump("松手写回配置后")

    print("\n配置里的顺序：")
    for t in win.config.tasks:
        print(f"  {t.order}. {t.name}")

    app.quit()


QTimer.singleShot(400, run)
app.exec()
