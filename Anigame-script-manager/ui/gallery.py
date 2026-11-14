# -*- coding: utf-8 -*-
"""昔涟美图网格（嵌在主界面里的页面，不是弹窗）。

设计上做的事
------------
**统一格子**：图有横有竖，全部按短边缩放后居中裁成正方形，
网格才不会高低不齐。

**等宽自适应**：窗口变宽时列数跟着变，而不是永远固定几列留一大片空白。

**懒加载 + 缓存**：目录可能有几百 MB，一次全读会卡住。
缩略图后台逐张生成，生成过的存着，来回切页面不重算。

**大图查看**：点开浮层，按屏幕比例缩放，点任意处 / Esc 关闭。

为什么不做成弹窗
----------------
弹窗会遮住底栏的「开始执行」，而且看完想回队列得先关窗。
嵌成页面后点一下标题栏的按钮就切回来，窗口本身不动。
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, QThread, Signal
from PySide6.QtGui import QImageReader, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ui import theme as theme_mod

EXTS = (".jpg", ".jpeg", ".png", ".webp", ".bmp")


def gallery_dir(custom: str = "") -> Path:
    """美图目录。自定义路径优先，其次程序旁的 Cyrene/。"""
    if custom:
        return Path(custom).expanduser()
    try:
        from ui.paths import data_dir, resource_dir

        for base in (data_dir(), resource_dir()):
            p = base / "Cyrene"
            if p.is_dir():
                return p
    except Exception:
        pass
    return Path("Cyrene")


def list_images(custom: str = "") -> list[Path]:
    d = gallery_dir(custom)
    if not d.is_dir():
        return []
    files = [p for p in d.iterdir() if p.is_file() and p.suffix.lower() in EXTS]
    files.sort(key=lambda p: p.name)
    return files


def _load_thumb(path: Path, target: int) -> QPixmap:
    """读成正方形缩略图：先按短边缩放到 target，再居中裁切。

    先缩后裁是关键：直接用 QImageReader 的 setScaledSize 能在解码阶段
    就缩小，不会把 30 MB 的原图整个读进内存。
    """
    reader = QImageReader(str(path))
    reader.setAutoTransform(True)
    size = reader.size()
    if size.isValid() and size.width() > 0 and size.height() > 0:
        w, h = size.width(), size.height()
        scale = target / min(w, h)
        if scale < 1.0:
            reader.setScaledSize(QSize(max(1, int(w * scale)), max(1, int(h * scale))))

    img = reader.read()
    if img.isNull():
        return QPixmap()

    pm = QPixmap.fromImage(img)
    side = min(pm.width(), pm.height())
    x = (pm.width() - side) // 2
    y = (pm.height() - side) // 2
    return pm.copy(x, y, side, side)


def _load_view(path: Path, max_side: int) -> QPixmap:
    """读大图，等比缩放到 max_side 以内。"""
    reader = QImageReader(str(path))
    reader.setAutoTransform(True)
    size = reader.size()
    if size.isValid() and size.width() > 0 and size.height() > 0:
        w, h = size.width(), size.height()
        scale = max_side / max(w, h)
        if scale < 1.0:
            reader.setScaledSize(QSize(int(w * scale), int(h * scale)))
    img = reader.read()
    return QPixmap() if img.isNull() else QPixmap.fromImage(img)


class _ThumbLoader(QThread):
    """后台生成缩略图。一次读一张，边读边发信号。"""

    ready = Signal(int, QPixmap)

    def __init__(self, files: list[Path], size: int, parent=None):
        super().__init__(parent)
        self._files = files
        self._size = size
        self._stop = False

    def stop(self) -> None:
        self._stop = True

    def run(self) -> None:
        for i, f in enumerate(self._files):
            if self._stop:
                return
            pm = _load_thumb(f, self._size)
            if not pm.isNull():
                self.ready.emit(i, pm)


class _Tile(QFrame):
    """一个格子。"""

    clicked = Signal(int)

    def __init__(self, index: int, path: Path, size: int, parent=None):
        super().__init__(parent)
        self.setObjectName("ThumbTile")
        self.setFixedSize(size + 10, size + 10)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._index = index

        lay = QVBoxLayout(self)
        lay.setContentsMargins(5, 5, 5, 5)
        lay.setSpacing(0)

        self._img = QLabel()
        self._img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._img.setFixedSize(size, size)
        lay.addWidget(self._img)

        self.setToolTip(path.name)

    def set_pixmap(self, pm: QPixmap) -> None:
        self._img.setPixmap(pm)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._index)


class _Viewer(QDialog):
    """大图浮层。点任意处或 Esc 关闭。"""

    def __init__(self, pixmap: QPixmap, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("ImageViewer")
        self.setWindowTitle(title)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setModal(True)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel()
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setPixmap(pixmap)
        lay.addWidget(lbl)
        self.resize(pixmap.width(), pixmap.height())

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self.accept()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.accept()
            return
        super().keyPressEvent(event)


class GalleryGrid(QWidget):
    """可嵌进页面的图片网格。"""

    THUMB = 148
    MIN_TILE = 158          # 缩略图 + 边距，用来算一行能放几个

    def __init__(self, theme: theme_mod.Theme, parent: QWidget | None = None):
        super().__init__(parent)
        self._theme = theme
        self._files: list[Path] = []
        self._custom = ""
        self._thumb_cache: dict[tuple[str, int], QPixmap] = {}
        self._loader: _ThumbLoader | None = None
        self._cols = 0
        self._tiles: list[_Tile] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setObjectName("GalleryScroll")
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._inner = QWidget()
        self._inner.setObjectName("GalleryInner")
        self._grid = QGridLayout(self._inner)
        self._grid.setContentsMargins(0, 0, 6, 0)
        self._grid.setSpacing(12)
        self._grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._scroll.setWidget(self._inner)
        outer.addWidget(self._scroll, 1)

        self._empty = QLabel("")
        self._empty.setObjectName("SectionHint")
        self._empty.setWordWrap(True)
        self._empty.setVisible(False)
        outer.addWidget(self._empty)

    # ---- 对外 ----
    def reload(self, custom: str = "") -> None:
        """重新扫描目录。切回画廊页时调用。

        只在目录变了或还没扫过时才重建——否则每次切页面都会重新
        生成一遍缩略图，白费功夫。
        """
        if custom == self._custom and self._files:
            return
        self._custom = custom
        self._stop_loader()
        self._files = list_images(custom)
        self._thumb_cache.clear()
        self._rebuild_tiles()

    def count(self) -> int:
        return len(self._files)

    # ---- 内部 ----
    def _stop_loader(self) -> None:
        if self._loader is not None:
            self._loader.stop()
            self._loader.wait(800)
            self._loader = None

    def _clear_grid(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._tiles = []

    def _calc_cols(self) -> int:
        width = self._scroll.viewport().width()
        if width <= 0:
            width = self.width()
        return max(1, (max(width, 200) - 20) // self.MIN_TILE)

    def _layout_tiles(self) -> None:
        cols = self._calc_cols()
        self._cols = cols
        self._clear_grid()
        for i, f in enumerate(self._files):
            tile = _Tile(i, f, self.THUMB)
            tile.clicked.connect(self._open_viewer)
            self._grid.addWidget(tile, i // cols, i % cols)
            self._tiles.append(tile)
            pm = self._thumb_cache.get((str(f), self.THUMB))
            if pm is not None:
                tile.set_pixmap(pm)

    def _rebuild_tiles(self) -> None:
        self._clear_grid()

        if not self._files:
            target = gallery_dir(self._custom)
            self._empty.setText(
                f"这个目录里没有图片：\n{target}\n\n"
                "去「设置 → 画廊」改路径，支持 jpg / png / webp / bmp。"
            )
            self._empty.setVisible(True)
            self._scroll.setVisible(False)
            return

        self._empty.setVisible(False)
        self._scroll.setVisible(True)
        self._layout_tiles()

        # 缓存里没有的才需要生成
        pending = [
            i for i, f in enumerate(self._files)
            if (str(f), self.THUMB) not in self._thumb_cache
        ]
        if not pending:
            return

        self._loader = _ThumbLoader([self._files[i] for i in pending], self.THUMB, self)
        # 信号带的是「在 pending 里的下标」，要映射回真实下标
        self._loader.ready.connect(lambda idx, pm: self._on_thumb(pending, idx, pm))
        self._loader.start()

    def _on_thumb(self, pending: list[int], sub_index: int, pm: QPixmap) -> None:
        if not (0 <= sub_index < len(pending)):
            return
        real = pending[sub_index]
        self._thumb_cache[(str(self._files[real]), self.THUMB)] = pm
        if 0 <= real < len(self._tiles):
            self._tiles[real].set_pixmap(pm)

    def _open_viewer(self, index: int) -> None:
        if not (0 <= index < len(self._files)):
            return
        screen = self.screen()
        max_side = 900
        if screen is not None:
            geo = screen.availableGeometry()
            max_side = int(min(geo.width(), geo.height()) * 0.72)
        pm = _load_view(self._files[index], max_side)
        if pm.isNull():
            return
        _Viewer(pm, self._files[index].name, self).exec()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        # 列数变了才重排，否则每次 resize 都在重建控件
        if self._files and self._calc_cols() != self._cols:
            self._layout_tiles()
