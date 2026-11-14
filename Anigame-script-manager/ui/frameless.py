# -*- coding: utf-8 -*-
"""无边框窗口的辅助：拖动移动、边缘缩放、自绘按钮。

为什么需要这个
--------------
原来的窗口是系统原生标题栏，在深色界面上会留一条白带，
和下面整片深色割裂。要统一观感就得去掉系统边框自己画。

去掉之后系统不再提供：
    - 拖动标题栏移动窗口
    - 拖边框调整大小
    - 双击标题栏最大化
    - 最小化 / 最大化 / 关闭 按钮

这些都得自己做。放在单独文件里，免得 MainWindow 越堆越大。

实现要点
--------
**拖动**：鼠标按下时记下「鼠标相对窗口左上角的偏移」，移动时用
`globalPos - 偏移` 反算窗口位置。不能用「每次移动加 delta」——
那样会因为浮点误差累积而抖动。

**缩放**：判断鼠标是否落在窗口四边附近的窄带里（EDGE 像素），
按下后按方向计算新的 geometry。窗口最大化时不允许缩放。

**按钮**：三个小按钮，悬停变色，关闭按钮悬停变红——这是桌面软件的
通用约定，不需要自己发明。
"""
from __future__ import annotations

from PySide6.QtCore import QObject, QPoint, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget


# 鼠标进入这个宽度的边界带就能拖拽缩放了
EDGE = 6


class WindowButton(QWidget):
    """自绘的窗口控制按钮（最小化 / 最大化 / 关闭）。

    为什么不用 QPushButton：这三个按钮画的是图形不是文字，
    而且关闭键悬停要变红——用 QSS 的话得写一堆 border-image，
    不如自己画两笔直接。
    """

    MINIMIZE = "min"
    MAXIMIZE = "max"
    CLOSE = "close"

    def __init__(self, kind: str, parent: QWidget | None = None):
        super().__init__(parent)
        self._kind = kind
        self._hover = False
        self.setFixedSize(46, 32)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        tips = {
            self.MINIMIZE: "最小化",
            self.MAXIMIZE: "最大化",
            self.CLOSE: "关闭",
        }
        self.setToolTip(tips.get(kind, ""))

    def enterEvent(self, event) -> None:  # noqa: N802
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        w, h = self.width(), self.height()

        # 悬停底色：关闭键用红，其余用淡白
        if self._hover:
            if self._kind == self.CLOSE:
                p.fillRect(self.rect(), QColor(224, 108, 126))
            else:
                p.fillRect(self.rect(), QColor(255, 255, 255, 30))

        # 图标颜色：关闭键悬停时用白色，其余保持浅灰
        color = QColor("#FFFFFF") if (self._hover and self._kind == self.CLOSE) else QColor(230, 225, 238)
        pen = QPen(color, 1.2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)

        cx, cy = w / 2.0, h / 2.0
        size = 5.0

        if self._kind == self.MINIMIZE:
            p.drawLine(QPoint(int(cx - size), int(cy) + 3), QPoint(int(cx + size), int(cy) + 3))
        elif self._kind == self.MAXIMIZE:
            p.drawRect(int(cx - size), int(cy - size + 1), int(size * 2), int(size * 2) - 1)
        else:  # CLOSE
            p.drawLine(QPoint(int(cx - size), int(cy - size)), QPoint(int(cx + size), int(cy + size)))
            p.drawLine(QPoint(int(cx + size), int(cy - size)), QPoint(int(cx - size), int(cy + size)))

        p.end()


class FramelessHelper:
    """给一个无边框窗口加上拖动、缩放、双击最大化。

    用法：在 MainWindow.__init__ 里 `self._frame = FramelessHelper(self)`，
    然后在鼠标事件里转发给它。
    """

    def __init__(self, window: QWidget, drag_area: QWidget | None = None):
        self._win = window
        self._drag_area = drag_area
        self._drag_offset: QPoint | None = None
        self._resize_edge = ""
        self._resize_start = None
        self._resize_geo = None

        if drag_area is not None:
            self.bind_drag_area(drag_area)

    def bind_drag_area(self, area: QWidget) -> None:
        """把一块区域变成「按住可以拖动窗口」。

        用事件过滤器而不是子类化：标题栏是 TitleBar（自绘控件），
        再包一层 class 不划算。过滤器只接 MouseButton/MouseMove，
        其余事件照常往下传，所以里面的按钮还是能正常点。
        """
        self._drag_area = area
        area.installEventFilter(_DragFilter(self))
        area.setMouseTracking(True)

    # ---- 拖动 ----
    def start_drag(self, global_pos: QPoint) -> None:
        """开始拖动。记下鼠标相对窗口左上角的偏移。"""
        if self._win.isMaximized():
            return
        self._drag_offset = global_pos - self._win.frameGeometry().topLeft()

    def do_drag(self, global_pos: QPoint) -> None:
        if self._drag_offset is None:
            return
        self._win.move(global_pos - self._drag_offset)

    def end_drag(self) -> None:
        self._drag_offset = None

    # ---- 缩放 ----
    @staticmethod
    def edge_at(local_pos: QPoint, width: int, height: int) -> str:
        """判断点落在窗口哪条边上。空字符串表示不在边缘。"""
        x, y = local_pos.x(), local_pos.y()
        left = x <= EDGE
        right = x >= width - EDGE
        top = y <= EDGE
        bottom = y >= height - EDGE

        if top and left:
            return "topleft"
        if top and right:
            return "topright"
        if bottom and left:
            return "bottomleft"
        if bottom and right:
            return "bottomright"
        if left:
            return "left"
        if right:
            return "right"
        if top:
            return "top"
        if bottom:
            return "bottom"
        return ""

    def start_resize(self, edge: str, global_pos: QPoint) -> None:
        if not edge or self._win.isMaximized():
            return
        self._resize_edge = edge
        self._resize_start = global_pos
        self._resize_geo = self._win.geometry()

    def do_resize(self, global_pos: QPoint) -> None:
        if not self._resize_edge or self._resize_start is None or self._resize_geo is None:
            return
        delta = global_pos - self._resize_start
        geo = self._resize_geo
        left, top, right, bottom = geo.left(), geo.top(), geo.right(), geo.bottom()

        if "left" in self._resize_edge:
            left = min(left + delta.x(), right - 400)
        if "right" in self._resize_edge:
            right = max(right + delta.x(), left + 400)
        if "top" in self._resize_edge:
            top = min(top + delta.y(), bottom - 300)
        if "bottom" in self._resize_edge:
            bottom = max(bottom + delta.y(), top + 300)

        self._win.setGeometry(left, top, right - left, bottom - top)

    def end_resize(self) -> None:
        self._resize_edge = ""
        self._resize_start = None
        self._resize_geo = None


class _DragFilter(QObject):
    """装在标题栏上的事件过滤器，负责把鼠标动作转给 FramelessHelper。

    单独一个类是为了不污染 MainWindow 的 eventFilter（那里已经处理了
    拖动排序的把手）。

    必须继承 QObject —— installEventFilter 要求过滤器本身是 QObject，
    普通 Python 对象会抛 "called with wrong argument types"。
    """

    def __init__(self, helper: FramelessHelper):
        super().__init__()
        self._helper = helper

    def eventFilter(self, obj, event):  # noqa: N802
        etype = event.type()

        if etype == event.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            self._helper.start_drag(event.globalPosition().toPoint())
            return True

        if etype == event.Type.MouseMove and event.buttons() & Qt.MouseButton.LeftButton:
            self._helper.do_drag(event.globalPosition().toPoint())
            return True

        if etype == event.Type.MouseButtonRelease:
            self._helper.end_drag()
            return True

        if etype == event.Type.MouseButtonDblClick:
            win = self._helper._win
            if win.isMaximized():
                win.showNormal()
            else:
                win.showMaximized()
            return True

        return False
