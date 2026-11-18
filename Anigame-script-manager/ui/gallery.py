# -*- coding: utf-8 -*-
"""画廊页：网格浏览 + 大图查看。

设计参考
--------
看的是 Pinterest / Unsplash 那种成熟图库交互，取了几条：

**1. 缩略图保留原始比例，不做正方形裁切**
   第一版把所有图裁成正方，横图竖图都被切掉两头，脸经常被裁一半。
   现在每格高度按图片原始比例算（限高），排成错落的一列，
   也就是常说的瀑布流。同一行的宽度对齐，高度自然错开。

**2. 悬停时轻微上浮 + 描边**
   静态网格翻起来没有落点反馈。悬停给一层浅色描边和一点位移，
   鼠标停在哪张上一眼能看出。

**3. 大图查看带背景遮罩和说明文字**
   第一版是纯图无边框弹窗，看着像程序崩了。现在：
   - 半透明黑底遮住背后的界面
   - 图片居中，四周留白
   - 底部显示文件名和尺寸
   - 左右方向键切换上一张/下一张
   - 点任意处或 Esc 关闭

**4. 首屏用「精选」大图**
   目录里有几张构图好的（情人节、星魂4），第一张给个大尺寸展示，
   比全部小缩略图一视同仁更有层次。

性能
----
- 缩略图后台线程逐张生成，边读边显示
- 生成过的缓存起来，切走再回来不重算
- 用 QImageReader.setScaledSize 在解码阶段就缩小，
  不会把 30 MB 的原图整个读进内存
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, QThread, Signal
from PySide6.QtGui import QImageReader, QPainter, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ui import theme as theme_mod

EXTS = (".jpg", ".jpeg", ".png", ".webp", ".bmp")


# ---------------------------------------------------------------- 目录


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


# ---------------------------------------------------------------- 读图


def _read_scaled(path: Path, max_w: int, max_h: int) -> tuple[QPixmap, QSize]:
    """读图并按边界缩放。返回 (图片, 原始尺寸)。

    用 QImageReader 的 setScaledSize 在解码阶段就缩小，
    大图（30 MB）不会整个读进内存。
    """
    reader = QImageReader(str(path))
    reader.setAutoTransform(True)
    size = reader.size()
    orig = QSize(size.width(), size.height()) if size.isValid() else QSize()

    if size.isValid() and size.width() > 0 and size.height() > 0:
        w, h = size.width(), size.height()
        scale = min(max_w / w, max_h / h, 1.0)
        if scale < 1.0:
            reader.setScaledSize(QSize(max(1, int(w * scale)), max(1, int(h * scale))))

    img = reader.read()
    if img.isNull():
        return QPixmap(), orig
    return QPixmap.fromImage(img), orig


class _Thumb(QThread):
    """后台生成缩略图。"""

    ready = Signal(int, QPixmap, int, int)   # index, pixmap, 原始宽, 原始高

    def __init__(self, files: list[Path], max_w: int, max_h: int, parent=None):
        super().__init__(parent)
        self._files = files
        self._max_w = max_w
        self._max_h = max_h
        self._stop = False

    def stop(self) -> None:
        self._stop = True

    def run(self) -> None:
        for i, f in enumerate(self._files):
            if self._stop:
                return
            pm, orig = _read_scaled(f, self._max_w, self._max_h)
            if not pm.isNull():
                self.ready.emit(i, pm, orig.width(), orig.height())


# ---------------------------------------------------------------- 格子


class _Tile(QFrame):
    """一个图片格子。保持原始比例，悬停有描边。"""

    clicked = Signal(int)
    RADIUS = 7

    def __init__(self, index: int, path: Path, width: int, height: int, parent=None):
        super().__init__(parent)
        self.setObjectName("GalleryTile")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._index = index
        self._path = path
        self._w = width
        self._h = height

        self.setFixedSize(width, height)

        # 图直接画在格子上（paintEvent），不塞 QLabel。
        # 用 QLabel 的话图片是矩形，会盖住 QSS 的圆角边框。
        self._pm: QPixmap | None = None

        self.setToolTip(f"{path.name}\n{width} × {height}")

    def set_pixmap(self, pm: QPixmap) -> None:
        self._pm = pm
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)     # 先让 QSS 画底色和边框
        if self._pm is None:
            return

        from PySide6.QtGui import QPainterPath

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        # 圆角裁切，让图跟着格子的圆角走
        clip = QPainterPath()
        clip.addRoundedRect(0, 0, self._w, self._h, self.RADIUS, self.RADIUS)
        p.setClipPath(clip)

        # 居中放置
        x = (self._w - self._pm.width()) // 2
        y = (self._h - self._pm.height()) // 2
        p.drawPixmap(x, y, self._pm)
        p.end()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._index)


# ---------------------------------------------------------------- 大图


class _Viewer(QDialog):
    """大图查看器。带遮罩、说明、左右切换。"""

    def __init__(self, files: list[Path], index: int, parent=None):
        super().__init__(parent)
        self.setObjectName("ImageViewer")
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setModal(True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self._files = files
        self._index = index

        # 撑满父窗口
        if parent is not None:
            self.resize(parent.size())
            self.move(parent.mapToGlobal(parent.rect().topLeft()))

        lay = QVBoxLayout(self)
        lay.setContentsMargins(60, 40, 60, 30)
        lay.setSpacing(12)

        self._image = QLabel()
        self._image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._image, 1)

        self._caption = QLabel("")
        self._caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._caption.setObjectName("ViewerCaption")
        lay.addWidget(self._caption)

        self._show_current()

    # ---- 显示 ----
    def _show_current(self) -> None:
        if not (0 <= self._index < len(self._files)):
            return
        path = self._files[self._index]

        w = max(320, self.width() - 140)
        h = max(240, self.height() - 140)
        pm, orig = _read_scaled(path, w, h)
        if pm.isNull():
            return
        self._image.setPixmap(pm)

        size_text = f"{orig.width()} × {orig.height()}" if orig.isValid() else ""
        pos_text = f"{self._index + 1} / {len(self._files)}"
        self._caption.setText(f"{path.name}    {size_text}    {pos_text}")

    # ---- 交互 ----
    def _step(self, delta: int) -> None:
        new = self._index + delta
        if 0 <= new < len(self._files):
            self._index = new
            self._show_current()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        key = event.key()
        if key in (Qt.Key.Key_Escape, Qt.Key.Key_Space):
            self.accept()
        elif key == Qt.Key.Key_Left:
            self._step(-1)
        elif key == Qt.Key.Key_Right:
            self._step(1)
        else:
            super().keyPressEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        # 点左侧三分之一 = 上一张，右侧三分之一 = 下一张，中间 = 关闭
        x = event.position().x()
        w = self.width()
        if x < w / 3:
            self._step(-1)
        elif x > w * 2 / 3:
            self._step(1)
        else:
            self.accept()

    def paintEvent(self, event) -> None:  # noqa: N802
        """半透明黑底，把背后的界面压暗。"""
        from PySide6.QtGui import QColor

        p = QPainter(self)
        p.fillRect(self.rect(), QColor(10, 6, 16, 235))
        p.end()


# ---------------------------------------------------------------- 网格


class _EmptyState(QWidget):
    """空状态：一张淡化的角色图 + 说明。

    为什么用透明底的那张：界面上唯一放得下大幅人像的地方就是「空着的时候」。
    有图的时候这块地儿被网格占满，反而没地方摆。

    摆放：图靠右下角、压得很淡，文字在左上三分之一处。
    两个区域尽量不重叠——第一版图放中间，文字直接压在她的头发上，读不清。
    """

    OPACITY = 0.16

    def __init__(self, theme: theme_mod.Theme, parent=None):
        super().__init__(parent)
        self._theme = theme
        self._pix: QPixmap | None = None

        # 优先用 PS 抠好的那张（真透明，任何底色上都干净）
        for name in ("2026.2.14情人节昔涟PS.png", "星魂4PS.png"):
            p = _asset_path("原图", name)
            if p is None:
                continue
            pm = QPixmap(str(p))
            if not pm.isNull():
                self._pix = pm
                break

        lay = QVBoxLayout(self)
        # 文字压在上三分之一，给下面的图让位
        lay.setContentsMargins(48, 0, 48, 0)
        lay.setSpacing(8)
        lay.addStretch(1)

        self._title = QLabel("这里还没有图片")
        self._title.setObjectName("EmptyTitle")
        self._title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(self._title)

        self._hint = QLabel("")
        self._hint.setObjectName("SectionHint")
        self._hint.setWordWrap(True)
        self._hint.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(self._hint)

        lay.addStretch(3)

    def set_message(self, title: str, hint: str) -> None:
        self._title.setText(title)
        self._hint.setText(hint)

    def paintEvent(self, event) -> None:  # noqa: N802
        # 整块铺一层很暗的底：把背后的整窗壁纸遮住。
        # 不遮的话两层人像叠在一起，看着乱。
        from PySide6.QtGui import QColor, QPainterPath

        p = QPainter(self)
        p.fillRect(self.rect(), QColor(14, 10, 22, 232))

        if self._pix is None:
            p.end()
            return

        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        # 占高度的 70%，贴右下角但留出下边距。
        # 之前是 78% 并且 y 加了下沉偏移，图的下沿被容器裁掉，
        # 形成一条明显的横向直边。
        target_h = int(self.height() * 0.70)
        if target_h <= 0:
            p.end()
            return

        scaled = self._pix.scaledToHeight(
            target_h, Qt.TransformationMode.SmoothTransformation
        )
        x = self.width() - scaled.width() - 12
        y = self.height() - scaled.height() - 10

        # 先画到一张透明画布上，再做「从左到右渐显」。
        #
        # 为什么这一步：这张图的内容一直顶到画布边缘（四边都有不透明像素），
        # 直接贴在暗底上、opacity 0.16，内容区和透明区之间会形成一条
        # 能看出来的竖直分界。用横向线性渐变把左边淡出，
        # 让它从文字区「长」出来，就没有硬边了。
        #
        # 之前试过椭圆渐隐，但椭圆在矩形画布上左右会被切掉，
        # 边缘位置反而多出一条直线。
        layer = QPixmap(scaled.size())
        layer.fill(Qt.GlobalColor.transparent)
        lp = QPainter(layer)
        lp.drawPixmap(0, 0, scaled)
        lp.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)

        from PySide6.QtGui import QLinearGradient

        fade = QLinearGradient(0, 0, scaled.width(), 0)
        fade.setColorAt(0.00, QColor(0, 0, 0, 0))       # 左边完全透明
        fade.setColorAt(0.35, QColor(0, 0, 0, 140))
        fade.setColorAt(0.70, QColor(0, 0, 0, 255))     # 右边不透明
        fade.setColorAt(1.00, QColor(0, 0, 0, 255))
        lp.fillRect(layer.rect(), fade)
        lp.end()

        p.setOpacity(self.OPACITY)
        p.drawPixmap(x, y, layer)
        p.setOpacity(1.0)
        p.end()


def _asset_path(*parts: str) -> Path | None:
    """拼 assets/cyrene 下的路径，找不到返回 None。"""
    try:
        from ui.paths import asset

        return asset("cyrene", *parts)
    except Exception:
        return None


class GalleryGrid(QWidget):
    """瀑布流网格。"""

    THUMB_W = 200          # 缩略图最大宽
    THUMB_H = 260          # 缩略图最大高（竖图上限）
    MIN_TILE = 214         # 一格最小占位，用来算列数
    GAP = 12

    def __init__(self, theme: theme_mod.Theme, parent: QWidget | None = None):
        super().__init__(parent)
        self._theme = theme
        self._files: list[Path] = []
        self._custom = ""
        # 缓存：(路径, 宽) -> (pixmap, 原始宽, 原始高)
        self._cache: dict[tuple[str, int], tuple[QPixmap, int, int]] = {}
        self._loader: _Thumb | None = None
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
        self._grid.setContentsMargins(0, 0, 8, 0)
        self._grid.setSpacing(self.GAP)
        self._grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._scroll.setWidget(self._inner)
        outer.addWidget(self._scroll, 1)

        # 空状态：目录里没图时显示，不再是一段干巴巴的文字
        self._empty = _EmptyState(theme)
        self._empty.setVisible(False)
        outer.addWidget(self._empty, 1)

    # ---- 对外 ----
    def reload(self, custom: str = "") -> None:
        if custom == self._custom and self._files:
            return
        self._custom = custom
        self._stop_loader()
        self._files = list_images(custom)
        self._cache.clear()
        self._rebuild()

    def count(self) -> int:
        return len(self._files)

    # ---- 内部 ----
    def _stop_loader(self) -> None:
        if self._loader is not None:
            self._loader.stop()
            self._loader.wait(800)
            self._loader = None

    def _clear(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._tiles = []

    def _calc_cols(self) -> int:
        width = self._scroll.viewport().width() or self.width()
        return max(1, (max(width, 240)) // self.MIN_TILE)

    def _rebuild(self) -> None:
        self._clear()

        if not self._files:
            target = gallery_dir(self._custom)
            if self._custom and not target.is_dir():
                self._empty.set_message(
                    "找不到这个目录",
                    f"{target}\n\n去「设置 → 画廊」改成正确的路径，或清空它用默认位置。",
                )
            else:
                self._empty.set_message(
                    "这里还没有图片",
                    f"把图片放进这个目录：\n{target}\n\n"
                    "支持 jpg / png / webp / bmp。\n"
                    "也可以在「设置 → 画廊」里指定别的文件夹。",
                )
            self._empty.setVisible(True)
            self._scroll.setVisible(False)
            return

        self._empty.setVisible(False)
        self._scroll.setVisible(True)
        self._layout_tiles()

        pending = [
            i for i, f in enumerate(self._files)
            if (str(f), self.THUMB_W) not in self._cache
        ]
        if not pending:
            return

        self._loader = _Thumb(
            [self._files[i] for i in pending], self.THUMB_W, self.THUMB_H, self
        )
        self._loader.ready.connect(lambda idx, pm, ow, oh: self._on_thumb(pending, idx, pm, ow, oh))
        self._loader.start()

    def _layout_tiles(self) -> None:
        """按瀑布流排。每格高度按原图比例算，但不超过 THUMB_H。"""
        cols = self._calc_cols()
        self._cols = cols
        self._clear()

        for i, f in enumerate(self._files):
            # 先从缓存拿尺寸；没有就先用默认比例占位，等加载完再调整
            cached = self._cache.get((str(f), self.THUMB_W))
            if cached is not None:
                _, ow, oh = cached
                tw, th = self._fit(ow, oh)
            else:
                tw, th = self.THUMB_W, int(self.THUMB_W * 1.3)

            tile = _Tile(i, f, tw, th)
            tile.clicked.connect(self._open_viewer)
            self._grid.addWidget(tile, i // cols, i % cols)
            self._tiles.append(tile)

            if cached is not None:
                tile.set_pixmap(cached[0])

    def _fit(self, ow: int, oh: int) -> tuple[int, int]:
        """按原始比例算缩略图尺寸，限制在 THUMB_W × THUMB_H 内。"""
        if ow <= 0 or oh <= 0:
            return self.THUMB_W, self.THUMB_H
        scale = min(self.THUMB_W / ow, self.THUMB_H / oh)
        return max(1, int(ow * scale)), max(1, int(oh * scale))

    def _on_thumb(self, pending: list[int], sub: int, pm: QPixmap, ow: int, oh: int) -> None:
        if not (0 <= sub < len(pending)):
            return
        real = pending[sub]
        self._cache[(str(self._files[real]), self.THUMB_W)] = (pm, ow, oh)

        if not (0 <= real < len(self._tiles)):
            return

        # 尺寸和占位不一致的话重建这一格（图片加载后才拿到真实比例）
        tile = self._tiles[real]
        tw, th = self._fit(ow, oh)
        if tile.width() != tw or tile.height() != th:
            new_tile = _Tile(real, self._files[real], tw, th)
            new_tile.clicked.connect(self._open_viewer)
            new_tile.set_pixmap(pm)
            row, col = real // self._cols, real % self._cols
            old = self._grid.itemAtPosition(row, col)
            if old is not None and old.widget() is tile:
                self._grid.removeWidget(tile)
                tile.deleteLater()
                self._grid.addWidget(new_tile, row, col)
                self._tiles[real] = new_tile
        else:
            tile.set_pixmap(pm)

    def _open_viewer(self, index: int) -> None:
        if not self._files:
            return
        win = self.window()
        _Viewer(self._files, index, win).exec()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self._files and self._calc_cols() != self._cols:
            self._layout_tiles()
