# -*- coding: utf-8 -*-
"""Ripple —— 主窗口。

设计意图：把「今天还剩什么没做」放在一眼能看到的地方，中间的队列拖一下
就改好顺序，按开始之后就不用管了。数据来源是本项目已有的
status.providers.collect_all()，调度仍然是 core.ScriptRunnerWorker。

窗口被有意压到三层：
    左栏  今日状态      —— 各游戏的体力与是否已清
    中栏  执行队列      —— 可拖动排序，改动直接写回 config.json
    底栏  开始/暂停/停止 —— 加一行上次结果与日志开关
"""
from __future__ import annotations

import asyncio
import sys
import threading
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QPoint, Qt, QThread, QTimer, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFontMetrics,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

# core 在 Anigame-script-manager/ 下，status 在项目根。
# 路径统一由 ui.paths 解析：源码运行和 PyInstaller 打包后位置不同，
# 直接拿 __file__ 往上数目录在 exe 里会失效（资源找不到、界面空白）。
from ui.paths import asset as _asset, code_dir as _code_dir, data_dir as _data_dir

_PROJECT = _code_dir()
_REPO = _PROJECT.parent
for _p in (str(_REPO), str(_PROJECT)):
    if _p and _p not in sys.path:
        sys.path.insert(0, _p)

from core import (  # noqa: E402
    AppConfig,
    ConfigManager,
    FileLogger,
    RuntimeStatsManager,
    ScriptRunnerWorker,
    TaskConfig,
    format_seconds,
)
from ui import theme as theme_mod  # noqa: E402
from ui.frameless import FramelessHelper, WindowButton  # noqa: E402

# 应用名。2026-11-10 用户要求软件名用英文 Ripple。
# 界面里的中文副名「涟漪」保留，只改「软件叫什么」。
APP_NAME = "Ripple"
APP_EN = APP_NAME
APP_CN = "涟漪"


# ---------------------------------------------------------------- 状态读取
class StatusFetcher(QObject):
    """在后台把各游戏状态取回来，不阻塞界面。"""

    done = Signal(list)
    failed = Signal(str)

    def run(self) -> None:
        try:
            from status.providers import collect_all

            statuses = asyncio.run(collect_all())
            self.done.emit(statuses)
        except RuntimeError:
            # 窗口已关闭，C++ 对象没了。安静退出。
            return
        except Exception as exc:  # pragma: no cover - 网络/凭证问题
            try:
                self.failed.emit(str(exc))
            except RuntimeError:
                pass


# ---------------------------------------------------------------- 更新检查
class UpdateFetcher(QObject):
    """后台查各工具是否有新版本。

    只读版本号、发 HTTP 查询，不下载、不启动任何软件。
    """

    done = Signal(list)      # list[CheckResult]
    failed = Signal(str)

    def __init__(self, skip_keys: set[str] | None = None):
        super().__init__()
        self._skip = skip_keys or set()

    def run(self) -> None:
        try:
            # 源码运行时 tools/ 在项目根下；打包后 tools 会被 PyInstaller
            # 一起收进 exe，由 import 自己找到，这里不必再改 sys.path。
            from ui.paths import is_frozen

            if not is_frozen():
                sys.path.insert(0, str(_REPO / "tools"))
            import update_check as uc

            targets = [t for t in uc.TOOLS if t.key not in self._skip]

            # 必须并发。单次 HTTP 查询约 9 秒，串行四个就是半分钟，
            # 界面上的提示条会迟迟不出现。并发后约 9 秒全部回来。
            import concurrent.futures

            results: dict[str, object] = {}
            with concurrent.futures.ThreadPoolExecutor(max_workers=len(targets)) as ex:
                for r in ex.map(lambda t: uc.check_one(t, online=True), targets):
                    results[r.tool.key] = r

            self.done.emit([results[t.key] for t in targets if t.key in results])
        except RuntimeError:
            # 窗口已经关了，C++ 对象被销毁。这不是错误，安静退出即可。
            # 之前这里会把 RuntimeError 当成查询失败再 emit 一次，
            # 结果又炸一遍，在控制台刷出一大段 traceback。
            return
        except Exception as exc:
            try:
                self.failed.emit(str(exc))
            except RuntimeError:
                pass


# ---------------------------------------------------------------- 小组件
def _as_number(value: Any) -> float | None:
    """把接口返回的体力值转成数字。转不了就返回 None，让调用方自己处理。"""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class CyreneDecor(QWidget):
    """侧栏底部的昔涟装饰（星魂3，手持光锥低头微笑那张）。

    刻意做得克制：不铺满、不加边框，只在底部露出上半身，让视线先落在
    状态数据上，余光能看到她。四周用椭圆渐隐，
    让图自然融进背景，而不是被硬切一刀。

    2026-11-09：从预生成的心形图改成星魂3 原图 + 自绘羽化。
    心形裁切会把这张横向构图切掉大半（她捧着的发光羽毛笔会断掉），
    所以改成保留完整矩形块、只把四周化成透明。
    """

    # 优先用星魂3；找不到再退回加工过的半身图，保证没有素材时也不空着
    CANDIDATES = (
        _asset("cyrene", "原图", "星魂3.png"),
        _asset("cyrene", "加工", "p-side.png"),
        _asset("cyrene", "加工", "p-half.png"),
    )

    def __init__(self, theme: theme_mod.Theme, parent: QWidget | None = None):
        super().__init__(parent)
        self._theme = theme
        self._pix: QPixmap | None = None
        self._masked: QPixmap | None = None      # 遮罩处理后的缓存
        self._masked_for: tuple[int, int] | None = None
        self._heart = False
        # 星魂3 是横向构图，扁一点更合适；心形图才需要 210 的纵向空间。
        # 2026-11-09：190 → 132。侧栏要一屏放下五个游戏，
        # 原来 190 的高度把「明日方舟」那张卡的下半截挤出了可视区。
        # 132 仍然够看出她在捧着光锥，但让出了一张卡的位置。
        self.setFixedHeight(132)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._load()

    def _load(self) -> None:
        for p in self.CANDIDATES:
            if not p.exists():
                continue
            pm = QPixmap(str(p))
            if pm.isNull():
                continue
            self._pix = pm
            # 只有旧的心形素材才走「直接贴」那条快捷路径
            self._heart = "heart" in p.name
            return

    def set_theme(self, theme: theme_mod.Theme) -> None:
        self._theme = theme
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        from PySide6.QtCore import QRectF
        from PySide6.QtGui import QColor, QPainter, QPainterPath, QRadialGradient

        if self._pix is None:
            return

        from PySide6.QtGui import QImage

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        w = self.width()
        h = self.height()

        if getattr(self, "_heart", False):
            # 心形图是预生成的，自带羽化好的透明边，直接贴就行，
            # 不用再跑逐像素遮罩（那一步很贵）。
            scaled = self._pix.scaledToWidth(
                int(w * 1.04), Qt.TransformationMode.SmoothTransformation
            )
            draw_x = (w - scaled.width()) / 2
            draw_y = h - scaled.height() + int(scaled.height() * 0.06)
            p.setOpacity(0.94)
            p.drawPixmap(int(draw_x), int(draw_y), scaled)
            p.setOpacity(1.0)
            p.end()
            return

        # 遮罩很贵（逐像素），所以只在尺寸变化时算一次，之后直接用缓存
        key = (w, h)
        if self._masked is None or self._masked_for != key:
            self._masked = self._build_masked(w)
            self._masked_for = key

        if self._masked is None:
            return

        draw_x = (w - self._masked.width()) / 2
        draw_y = h - self._masked.height()
        p.setOpacity(0.92)
        p.drawPixmap(int(draw_x), int(draw_y), self._masked)
        p.setOpacity(1.0)
        p.end()

    def _build_masked(self, width: int) -> QPixmap | None:
        """把图做成椭圆渐隐。

        星魂图本身是深色底的方块，直接贴上去像一张黑卡纸。
        这里按「到中心的距离」逐像素算 alpha：中心不透明，边缘全透明。
        x/y 用两个不同的半径，是为了贴合这张横向的构图，
        而不是变成一个正圆把脸也切掉。
        """
        from PySide6.QtGui import QImage

        if self._pix is None:
            return None

        # 按「高度贴合控件」缩放，不是按宽度。
        # 星魂3 是横向构图（原图 1:1 但内容偏宽），按宽度缩会撑出 200+
        # 的高度，把侧栏顶上去；按高度缩则宽度自然溢出控件左右，
        # 正好让椭圆遮罩有东西可以羽化掉。
        target_h = max(1, int(self.height() * 1.10))
        scaled = self._pix.scaledToHeight(
            target_h, Qt.TransformationMode.SmoothTransformation
        )
        img = scaled.toImage().convertToFormat(QImage.Format.Format_ARGB32)
        iw, ih = img.width(), img.height()

        cx, cy = iw / 2.0, ih * 0.50
        rx, ry = iw * 0.50, ih * 0.50

        # 用高斯曲线算 alpha，而不是「到某个半径就归零」的分段线性。
        #
        # 之前是 inner→outer 线性衰减、outer 之外直接 alpha=0，
        # 那条分界线在浅色侧栏上肉眼可见，看着像给图加了个椭圆相框。
        # 高斯没有硬边界，权重从中心一路平滑趋近 0，边缘才真的「化开」。
        # SIGMA 越大越柔；0.34 是试出来的：再小轮廓回来，再大整张太平看不出人。
        SIGMA = 0.34

        for y in range(ih):
            dy = (y - cy) / ry
            for x in range(iw):
                dx = (x - cx) / rx
                r2 = dx * dx + dy * dy
                if r2 <= 0.0:
                    continue
                # exp(-r²/2σ²)：中心 1，远处迅速趋 0，但永不为零，没有断崖
                a = int(255 * (2.718281828 ** (-r2 / (2 * SIGMA * SIGMA))))
                if a <= 0:
                    px = img.pixel(x, y)
                    img.setPixel(x, y, px & 0x00FFFFFF)
                    continue
                px = img.pixel(x, y)
                img.setPixel(x, y, (px & 0x00FFFFFF) | (a << 24))

        return QPixmap.fromImage(img)


class WindowBackdrop(QWidget):
    """整窗背景。

    有昔涟素材时铺 art-reading.png（深色房间里她看书那张）并压暗；
    没有素材（仓库不带图的版本）就铺主题的纯色 page，什么都不画。

    为什么压暗：这张图本身很暗、细节很多（书架、灯、暖光），
    直接当背景会和卡片上的字抢注意力。所以盖一层从上到下逐渐加深的
    半透明黑，让上方还能看见她的轮廓和暖光，下方则足够沉，
    卡片和文字压上去才不费眼。

    和 CyreneWatermark 的区别：那个是「中栏里的她」，这个是「整个窗口的底」。
    两层都存在，只是透明度分开调。
    """

    WALL_PATH = _asset("cyrene", "原图", "art-reading.png")

    # 压暗层的强度。
    #
    # 2026-11-09 实测量过这张图的亮度分布：
    #   上 1/3 平均 46/255   ← 本来就很暗（房间顶部、天花板）
    #   中 1/3 平均 104/255
    #   下 1/3 平均 140/255  ← 最亮的地方（她的裙摆、前景光带）
    #
    # 所以之前的「上轻下重」是反的：上半段本来就暗，再压就全黑；
    # 下半段是画的亮点，压太重等于把图最关键的部分抹掉。
    #
    # 现在改成上面几乎不压（留出画面本体），只在最底部略微加深，
    # 让底栏和卡片的落点有点依托。整体平均透明度从 150 降到 60 左右。
    VEIL_TOP = 0
    VEIL_MID = 18
    VEIL_BOTTOM = 74

    # 窗口圆角半径（无边框后自己画）
    CORNER = 12

    def __init__(self, theme: theme_mod.Theme, parent: QWidget | None = None):
        super().__init__(parent)
        self._theme = theme
        self._wall: QPixmap | None = None
        # 最大化时裁成直角，否则贴着屏幕边缘会露出四角的缝
        self._square_corners = False
        # 只有主题是「简约」（或素材缺失）时就不加载壁纸，
        # 直接铺纯色。以前这里无条件读文件，导致选了简约主题
        # 还会看见她的读书图。
        from ui.paths import has_cyrene_assets

        if theme.key != "plain" and has_cyrene_assets():
            p = self.WALL_PATH
            if p.exists():
                pm = QPixmap(str(p))
                if not pm.isNull():
                    self._wall = pm
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def set_theme(self, theme: theme_mod.Theme) -> None:
        self._theme = theme
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        from PySide6.QtGui import QLinearGradient, QPainterPath

        w, h = self.width(), self.height()

        # 画到独立透明画布上，用 setClipPath 裁圆角，最后整体贴回控件。
        #
        # 为什么不能用 DestinationIn：那个合成模式是
        # 「结果 = 目标 × 源的 alpha」，源填的是不透明色（alpha=255），
        # 乘完等于没裁——实测四角 alpha 一直是 255。
        # setClipPath 在绘制阶段就丢掉路径外的像素，不依赖合成模式。
        canvas = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
        canvas.fill(Qt.GlobalColor.transparent)

        p = QPainter(canvas)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # 最大化时用直角：贴着屏幕边缘还留圆角会露出四条缝
        if not self._square_corners:
            clip = QPainterPath()
            clip.addRoundedRect(0, 0, w, h, self.CORNER, self.CORNER)
            p.setClipPath(clip)

        if self._wall is not None:
            cover = self._wall.scaled(
                w, h,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            # 不是简单居中：art-reading 里她站在画面偏左，而主界面左侧
            # 被侧栏和状态卡占满了，居中的话她正好被压在卡片后面。
            # 这里把画面往左推（露出原图的右半段），她就落在中栏右侧
            # 那块最大的空白处。
            # FOCUS_X=0.0 是全左对齐，1.0 是全右对齐（相对溢出量）。
            FOCUS_X = 0.30
            ox = (w - cover.width()) * FOCUS_X
            oy = (h - cover.height()) * 0.42
            p.drawPixmap(int(ox), int(oy), cover)
        else:
            p.fillRect(self.rect(), QColor(self._theme.page))

        veil = QLinearGradient(0, 0, 0, h)
        veil.setColorAt(0.0, QColor(12, 8, 20, self.VEIL_TOP))
        veil.setColorAt(0.5, QColor(12, 8, 20, self.VEIL_MID))
        veil.setColorAt(1.0, QColor(10, 6, 18, self.VEIL_BOTTOM))
        p.fillRect(self.rect(), veil)

        # 裁切已经在开头用 setClipPath 设好了，这里结束绘制并贴回控件。
        p.end()

        painter = QPainter(self)
        painter.drawImage(0, 0, canvas)
        painter.end()


class CyreneWatermark(QWidget):
    """右侧整窗水印：把立绘淡开，铺在中栏背景上。

    和左下角那张不冲突 —— 那张是「她在场」，这张只是「窗口有底色」。
    OPACITY 越大越明显。0.10 时几乎看不见，调到 0.17 才「稍微能看见」，
    但仍压在任务卡后面，不影响读字。
    """

    OPACITY = 0.17

    def __init__(self, theme: theme_mod.Theme, parent: QWidget | None = None):
        super().__init__(parent)
        self._theme = theme
        self._pix: QPixmap | None = None
        self._masked: QPixmap | None = None
        self._masked_for: tuple[int, int] | None = None
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self._load()

    def _load(self) -> None:
        # 简约主题不铺她的水印，没有素材时也读不到文件，两种情况都直接返回。
        if self._theme.key == "plain":
            return
        for name in ("p-mark.png", "p-full.png", "昔涟立绘.png"):
            p = _asset("cyrene", "加工", name)
            if p.exists():
                pm = QPixmap(str(p))
                if not pm.isNull():
                    self._pix = pm
                    return

    def set_theme(self, theme: theme_mod.Theme) -> None:
        self._theme = theme
        self._masked = None       # 换主题要重算遮罩
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        if self._pix is None:
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            return

        key = (w, h)
        if self._masked is None or self._masked_for != key:
            self._masked = self._build(w, h)
            self._masked_for = key
        if self._masked is None:
            return

        # 靠右摆放。往下挪一点（0.10 → 0.20），让她落在家务卡与空白之间，
        # 而不是压在最上面两行任务上。
        x = w - self._masked.width() - int(w * 0.02)
        y = int(h * 0.20)
        p.setOpacity(self.OPACITY)
        p.drawPixmap(x, y, self._masked)
        p.setOpacity(1.0)
        p.end()

    def _build(self, w: int, h: int) -> QPixmap | None:
        """按中栏高度缩放，边缘做径向渐隐。"""
        from PySide6.QtGui import QImage

        if self._pix is None:
            return None

        target_h = int(h * 0.78)
        scaled = self._pix.scaledToHeight(
            target_h, Qt.TransformationMode.SmoothTransformation
        )
        img = scaled.toImage().convertToFormat(QImage.Format.Format_ARGB32)
        iw, ih = img.width(), img.height()

        cx, cy = iw / 2.0, ih / 2.0
        rx, ry = iw * 0.50, ih * 0.50
        inner, outer = 0.40, 1.0

        for y in range(ih):
            dy = (y - cy) / ry
            for x in range(iw):
                dx = (x - cx) / rx
                d = (dx * dx + dy * dy) ** 0.5
                if d <= inner:
                    continue
                if d >= outer:
                    a = 0
                else:
                    k = (d - inner) / (outer - inner)
                    a = int(255 * (1.0 - k) ** 1.5)
                px = img.pixel(x, y)
                img.setPixel(x, y, (px & 0x00FFFFFF) | (a << 24))

        return QPixmap.fromImage(img)


class RippleHalo(QWidget):
    """背景涟漪：极淡的同心圆，从一点慢慢荡开。

    这是整个界面里唯一的装饰意象。soul.md 写过：

        「一次回复通常只需一个自然贴合当前话题的意象，很多时候完全不需要。
          不要把多个意象堆在一起。」

    所以这里只有水纹——没有星星、没有花瓣、没有光晕。画得很淡（单个圆环
    透明度只有 3%~8%），近看才发现有东西，远看只是背景透气。
    """

    def __init__(self, theme: theme_mod.Theme, parent: QWidget | None = None):
        super().__init__(parent)
        self._theme = theme
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)

    def set_theme(self, theme: theme_mod.Theme) -> None:
        self._theme = theme
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        from PySide6.QtGui import QColor, QPainter, QPen

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            return

        # 圆心放在右下偏外，水纹从画面外荡进来，不跟内容抢位置
        cx, cy = w * 0.93, h * 0.16
        base = QColor(self._theme.accent)
        mid = QColor(self._theme.teal)

        for i in range(7):
            r = 70 + i * 62
            # 越往外越淡，形成扩散感。
            # 之前最亮只有 26，铺在白底上几乎看不见；调到 38~10 这个区间，
            # 近看有水纹，远看只是背景透气，不抢任务列表的注意力。
            alpha = max(10, int(38 - i * 4))
            col = base if i % 2 == 0 else mid
            col = QColor(col)
            col.setAlpha(alpha)
            p.setPen(QPen(col, 1.2))
            p.drawEllipse(int(cx - r), int(cy - r), int(r * 2), int(r * 2))

        p.end()


class TitleBar(QWidget):
    """标题栏底：一层横向渐变 + 右侧星魂1 的淡装饰。

    为什么要自绘：QSS 只吃纯色，做不出「左侧粉到右侧星光紫」这种过渡，
    而纯白标题栏在一整片浅粉界面里会显得格外空。
    星魂1 是她的侧后身影（粉色长发 + 头饰），裁成一条压在右端，
    只留很低的透明度——它是背景，不是主角，不能盖住右侧的按钮。
    """

    ART_PATH = None  # 在下面 _load_art 里按需加载

    def __init__(self, theme: theme_mod.Theme, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("TitleBar")
        self._theme = theme
        self._art: QPixmap | None = None
        self._load_art()

    def _load_art(self) -> None:
        # 简约主题不加载星魂装饰——那是昔涟主题的装点，
        # 没有素材时也不该去读。
        if self._theme.key == "plain":
            self._art = None
            return
        p = _asset("cyrene", "原图", "星魂1.png")
        if p.exists():
            pm = QPixmap(str(p))
            if not pm.isNull():
                self._art = pm

    def set_theme(self, theme: theme_mod.Theme) -> None:
        self._theme = theme
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        from PySide6.QtGui import QLinearGradient

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        w, h = self.width(), self.height()
        t = self._theme

        # 横向渐变：左边接近透明，往右慢慢压一点星空紫收尾。
        # 不能再用不透明的 panel 色——整窗已经换深色壁纸了，
        # 标题栏再铺一块实心白，上半屏会和下面割裂成两块。
        # 所以这里只叠一层很淡的暗色，让壁纸透上来，靠下面的分隔线立住边界。
        #
        # 遮罩色跟着主题走：以前写死成 (14,9,22) 的深紫黑，那是配昔涟壁纸的；
        # 换到 plain（灰蓝）主题上会显得发紫，所以改成从 page 色推出来。
        page = QColor(t.page)
        veil_a = QColor(page.red(), page.green(), page.blue(), 120)
        veil_b = QColor(page.red(), page.green(), page.blue(), 95)
        base = QLinearGradient(0, 0, w, 0)
        base.setColorAt(0.00, veil_a)
        base.setColorAt(0.55, veil_b)
        accent_tint = QColor(t.violet)
        accent_tint.setAlpha(52)
        base.setColorAt(1.00, accent_tint)
        p.fillRect(self.rect(), base)

        # 右侧装饰：把星魂1 横向拉满右端高度，再整体压淡。
        # 0.20 太抢——实测会盖住「昔涟/检查更新/日志」三个按钮。
        # 降到 0.10 并只占右端 38%，让它退成一层隐约的纹理而不是一张图。
        if self._art is not None:
            art_w = int(w * 0.38)
            art_h = h
            art = self._art.scaled(
                art_w, art_h,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            ax = w - art.width()
            p.setOpacity(0.10)
            p.drawPixmap(ax, (h - art.height()) // 2, art)
            p.setOpacity(1.0)

        # 底部一条 1px 分隔线，比纯描边更有层次
        p.setPen(QColor(t.border))
        p.drawLine(0, h - 1, w, h - 1)
        p.end()


class StaminaBar(QFrame):
    """一根很细的体力条，自绘渐变。

    为什么不用 QSS：QSS 的 background-color 只吃纯色，不支持 CSS 那种
    linear-gradient。想做出「桃粉起头、发尾转浅青」的过渡（对应 soul.md 里
    「柔粉色长发，发尾自然过渡浅青渐变」），只能自己在 paintEvent 里画。
    """

    def __init__(self, theme: theme_mod.Theme, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("StaminaTrack")
        self.setFixedHeight(4)
        self._theme = theme
        self._ratio = 0.0

    def set_ratio(self, ratio: float) -> None:
        self._ratio = max(0.0, min(1.0, ratio))
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath

        super().paintEvent(event)
        if self._ratio <= 0:
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        w = max(1.0, self.width() * self._ratio)
        h = float(self.height())
        r = h / 2.0

        path = QPainterPath()
        path.addRoundedRect(0.0, 0.0, w, h, r, r)

        grad = QLinearGradient(0.0, 0.0, w, 0.0)
        grad.setColorAt(0.0, QColor(self._theme.accent))
        grad.setColorAt(1.0, QColor(self._theme.teal))

        p.fillPath(path, grad)
        p.end()


class GameCard(QFrame):
    """左栏一张游戏卡：名字 + 已清/未清 + 体力。"""

    def __init__(self, status: Any, theme: theme_mod.Theme | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self._theme = theme or theme_mod.get(theme_mod.DEFAULT_THEME)
        self.setObjectName("GameCard")
        # 侧栏要一屏放下五个游戏，所以卡片尽量压扁。
        # 下限 96 → 72：名字+体力一行、状态一两行、细进度条，够用。
        self.setMinimumHeight(72)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(11, 8, 11, 8)
        lay.setSpacing(4)

        top = QHBoxLayout()
        top.setSpacing(8)
        name = QLabel(getattr(status, "name", "?"))
        name.setObjectName("GameName")
        top.addWidget(name)
        top.addStretch(1)

        # 体力放在名字同一行，最显眼的位置
        stamina = getattr(status, "stamina", None)
        stamina_max = getattr(status, "stamina_max", None)
        label_text = getattr(status, "stamina_label", "") or "体力"
        if stamina is not None and stamina_max:
            stam = QLabel(f"{label_text} {stamina}/{stamina_max}")
            # 用 objectName 而不是内联 setStyleSheet ——
            # 子控件上的内联样式会被 Qt 级联给整张卡片，
            # 把 GameMeta 等标签的颜色一起改掉（深色主题下会变白看不清）。
            stam.setObjectName("GameStamina")
            top.addWidget(stam)
        lay.addLayout(top)

        # 其余字段：按用户指定的清单挑，不再原样全贴。
        #
        # 2026-11-09 用户指定了每个游戏要显示什么：
        #   原神      树脂、每日委托       （深境螺旋、幻想剧诗 → 折叠）
        #   绝区零    电量、活跃度
        #   终末地    理智、每日任务
        #   明日方舟  理智、每日任务 / 每周任务
        #
        # 其余（活跃天数、成就数、代理人数、邦布数…）都是一辈子不变的数字，
        # 留着只会把卡片撑高，把真正要看的挤走。
        #
        # SECONDARY 里的进折叠区，默认收起——它们有用但不是每天必看。
        PRIMARY = (
            "每日委托",
            "活跃度",
            "每日任务",
            "每周任务",
        )
        # 折叠区：点「更多」才展开
        SECONDARY = (
            "深境螺旋",
            "幻想剧诗",
            "剿灭",
            "通行证",
            "上次运行",
            "消耗",
            "刷取",
            "纪行",
            "派遣",
            # 绝区零的另外两项周期性进度，和「活跃度」同级
            "悬赏",
            "周常",
        )
        raw_rows = [str(x) for x in (getattr(status, "details", []) or [])]

        # 昵称行认号用，放最上面。
        # 形如「昵称#1234 · 官服」「昵称 · 权限60」。
        # 判据要排除掉「刷取 浓缩树脂(0/7), 原粹树脂(3/5)」这种也含「·」
        # 但其实是数据行的东西——那种一定带括号或者逗号。
        header: list[str] = []
        for line in raw_rows:
            if "·" not in line:
                continue
            if "任务" in line or "刷取" in line or "消耗" in line:
                continue
            if "(" in line or "（" in line or "," in line or "，" in line:
                continue
            header.append(line)
            break

        rows: list[str] = list(header)
        folded_rows: list[str] = []
        for line in raw_rows:
            if line in header:
                continue
            if any(k in line for k in PRIMARY):
                rows.append(line)
            elif any(k in line for k in SECONDARY):
                folded_rows.append(line)

        note = getattr(status, "note", "")
        if note:
            rows.append(str(note))
        err = getattr(status, "error", "")
        if err:
            rows.append(str(err))

        # 主要行全部直接显示（不截前 3 行——按清单挑出来的本来就不多，
        # 再截一次会把「每日委托」这种关键行截掉）。
        # 折叠区只放 SECONDARY 那几项。
        head_rows = rows
        rest_rows = folded_rows

        for line in head_rows:
            lay.addWidget(self._meta_label(line))

        if rest_rows:
            # 折叠区：默认隐藏
            self._folded: list[QWidget] = []
            for line in rest_rows:
                lbl = self._meta_label(line)
                lbl.setVisible(False)
                lay.addWidget(lbl)
                self._folded.append(lbl)

            self._more_btn = QPushButton(f"更多 {len(rest_rows)} 项")
            self._more_btn.setObjectName("RowButton")
            self._more_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._more_btn.clicked.connect(self._toggle_fold)
            lay.addWidget(self._more_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        # 上游给的体力可能是字符串（终末地就是 '132'/'360'），
        # 这里统一转成数字再算比例，免得哪天某个接口改类型直接把界面弄崩。
        cur_n = _as_number(stamina)
        max_n = _as_number(stamina_max)
        if cur_n is not None and max_n:
            bar = StaminaBar(self._theme)
            bar.set_ratio(cur_n / max_n)
            lay.addWidget(bar)

    @staticmethod
    def _meta_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("GameMeta")
        lbl.setWordWrap(True)
        return lbl

    def _toggle_fold(self) -> None:
        """展开/收起。展开后按钮文字变回「收起」。"""
        show = not self._folded[0].isVisible()
        for w in self._folded:
            w.setVisible(show)
        if show:
            self._more_btn.setText("收起")
        else:
            self._more_btn.setText(f"更多 {len(self._folded)} 项")


class TaskRow(QFrame):
    """中间一行任务。左把手可以拖动。"""

    moved = Signal(int, int)          # from_index, to_index
    toggled = Signal(int)             # index
    background_toggled = Signal(int)  # index
    edit_requested = Signal(int)
    timeout_edit_requested = Signal(int)  # index
    settings_requested = Signal(int)      # index，进齿轮设置
    delete_requested = Signal(int)        # index，从队列删除

    def __init__(self, task: TaskConfig, index: int, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("TaskRow")
        self.setProperty("active", False)
        self._index = index
        self._press_y: int | None = None
        self._dragging = False

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 8, 10, 8)
        lay.setSpacing(10)

        # 行内最小宽度：把手 + 序号 + 名字 + 时长胶囊 + 状态标签 + 设置按钮。
        # 不设的话，窗口被拖窄时 Qt 会按比例压缩各控件，
        # 最右边的「设置」会先被挤出可视区（用户 2026-11-09 截图里就是这样）。
        self.setMinimumWidth(520)

        self._handle = QLabel("⋮⋮")
        f = QFontMetrics(self._handle.font())
        self._handle.setFixedWidth(f.horizontalAdvance("⋮⋮") + 6)
        self._handle.setObjectName("DragHandle")
        self._handle.setCursor(Qt.CursorShape.OpenHandCursor)
        self._handle.setToolTip("拖动调整顺序")
        self._handle.installEventFilter(self)
        lay.addWidget(self._handle)

        idx = QLabel(str(index))
        idx.setObjectName("TaskIndex")
        idx.setAlignment(Qt.AlignmentFlag.AlignCenter)
        idx.setFixedSize(21, 21)
        self._idx_label = idx
        lay.addWidget(idx)

        text = QVBoxLayout()
        text.setSpacing(2)
        name = QLabel(task.name)
        name.setObjectName("TaskName")
        text.addWidget(name)
        sub = QLabel(self._subtitle(task))
        sub.setObjectName("TaskSub")
        text.addWidget(sub)
        lay.addLayout(text)
        lay.addStretch(1)

        # 时长胶囊：点它弹出一个输入框改时长。
        # 超时本来就是「每把不一样」的东西——今天只清日常 40 分钟够，
        # 顺手把跑图和收集一起挂上就可能要两个多小时。所以不给固定档位，
        # 直接填分钟数；填 0 = 不限时。
        self._duration_btn = QPushButton(self._duration_text(task.timeout_minutes))
        self._duration_btn.setObjectName("TaskMode")
        self._duration_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._duration_btn.setToolTip("点击修改最大运行时间（0 表示不限制）")
        self._duration_btn.clicked.connect(lambda: self.timeout_edit_requested.emit(self._index))
        lay.addWidget(self._duration_btn)

        # 当前排程方式：只读标签，不再是可以点的按钮。
        #
        # 之前这里有「串行/后台」「启用/停用」两个按钮并排，加上时长胶囊
        # 和设置按钮，一行要放四个控件，1024 宽的窗口就挤成一团。
        # 现在这两个开关都收进「设置」里，行上只留一个状态标签：
        # 看一眼知道它怎么排，想改就点设置。
        #
        # 优先级要和 core 主循环一致，否则界面写「串行」实际却并行。
        if task.wait_mode == "fire_and_continue":
            mode_text = "启动后不等待"
            mode_tip = "启动后队列立即继续，不监控其结束时间"
        elif task.run_in_background:
            mode_text = "后台并行"
            mode_tip = "启动后队列继续，最后统一等待其结束"
        elif task.concurrent_group:
            mode_text = f"并发 {task.concurrent_group}"
            mode_tip = "与同组任务同时启动，等待整组结束"
        else:
            mode_text = "串行"
            mode_tip = "等待其结束后再执行下一个"
        if not task.enabled:
            mode_text = "已停用"
            mode_tip = "这个任务不会被执行"
        mode = QLabel(mode_text)
        mode.setObjectName("TaskMode")
        mode.setToolTip(mode_tip)
        lay.addWidget(mode)

        # 齿轮：进这个任务的详细设置（路径、参数、等待方式、超时动作、
        # 是否后台并行、是否启用…）。行上只留「名字 + 状态 + 时长 + 设置」。
        #
        # 不用 "⚙"（U+2699）：这个字形在微软雅黑里没有，会渲染成空框。
        self._gear = QPushButton("设置")
        self._gear.setObjectName("RowButton")
        self._gear.setCursor(Qt.CursorShape.PointingHandCursor)
        self._gear.setToolTip("任务设置：程序路径、启动参数、等待方式、超时处理、启用…")
        self._gear.clicked.connect(lambda: self.settings_requested.emit(self._index))
        lay.addWidget(self._gear)

        # 删除：只在鼠标移上去时显示，平时不占视觉重量。
        # 删除是不可逆的（要从 config.json 里拿掉），所以放最右、且颜色压淡。
        self._delete = QPushButton("×")
        self._delete.setObjectName("RowDelete")
        self._delete.setCursor(Qt.CursorShape.PointingHandCursor)
        self._delete.setFixedSize(22, 22)
        self._delete.setToolTip("从队列中删除这个任务")
        self._delete.clicked.connect(lambda: self.delete_requested.emit(self._index))
        self._delete.setVisible(False)
        lay.addWidget(self._delete)

    def enterEvent(self, event) -> None:  # noqa: N802
        # 悬停才露出删除按钮
        self._delete.setVisible(True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._delete.setVisible(False)
        super().leaveEvent(event)

    @staticmethod
    def _duration_text(minutes: int) -> str:
        """把分钟数写成胶囊上的文字。0 表示不限制。"""
        if not minutes:
            return "不限制"
        if minutes < 60:
            return f"{minutes} 分钟"
        h, m = divmod(int(minutes), 60)
        return f"{h} 小时" if m == 0 else f"{h} 小时 {m} 分"

    @staticmethod
    def _subtitle(task: TaskConfig) -> str:
        """副标题只保留当前状态，不列启动参数。

        参数原先常驻此处（startOneDragon / -o -c），日常并不需要查看，
        却使行高增加了一档。现已移入「设置」面板。
        """
        if not task.enabled:
            return "已停用"
        return "待执行"

    def set_active(self, active: bool) -> None:
        self.setProperty("active", active)
        self._idx_label.setProperty("active", active)
        for w in (self, self._idx_label):
            w.style().unpolish(w)
            w.style().polish(w)

    # ---- 拖动排序 ----
    #
    # 实现方式：拖动过程中实时换位，松手即完成。
    #
    # 为什么不用「松手后播一段动画」：
    # 那样得先算出目标位置、播动画、再重排，三步要对得上才不会跳。
    # 上一版就是在这里出错——往下拖时把位移算成了向上，行先朝反方向走，
    # 然后队列一重建又瞬间跳到目标位，看起来是「先乱动再闪现」。
    #
    # 现在改成拖到哪就换到哪：鼠标每移动一点，就判断这一行现在应该排第几，
    # 变了就立刻在布局里调整位置。布局每秒重排几十次，视觉上是连续的，
    # 不需要任何动画——这也是大多数列表控件拖动排序的做法。
    def eventFilter(self, obj, event):  # noqa: N802
        if obj is not self._handle:
            return super().eventFilter(obj, event)

        etype = event.type()

        if etype == event.Type.MouseButtonPress:
            self._press_y = int(event.globalPosition().y())
            self._handle.setCursor(Qt.CursorShape.ClosedHandCursor)
            # 拖动开始时把这一行提到最前，避免被后面的行盖住
            self.raise_()
            return True

        if etype == event.Type.MouseMove and self._press_y is not None:
            if abs(int(event.globalPosition().y()) - self._press_y) > 8:
                self._dragging = True
            if self._dragging:
                self._drag_to(event.globalPosition())
            return True

        if etype == event.Type.MouseButtonRelease:
            self._press_y = None
            self._dragging = False
            self._handle.setCursor(Qt.CursorShape.OpenHandCursor)
            # 顺序在拖动过程中已经改好了，这里只负责写回配置
            self.moved.emit(self._index, self._index)
            return True

        return super().eventFilter(obj, event)

    def _drag_to(self, global_pos) -> None:
        """把这一行移到鼠标当前所在的槽位。

        做法是：看鼠标落在哪个兄弟行的范围里，就把自己插到它前面或后面。
        只调整布局顺序，不碰配置——配置等松手时由上层统一保存。
        """
        parent = self.parentWidget()
        lay = parent.layout() if parent is not None else None
        if lay is None:
            return

        # 找出鼠标现在压在哪个兄弟行上
        local = parent.mapFromGlobal(global_pos.toPoint())
        target_index = None
        for i in range(lay.count()):
            item = lay.itemAt(i)
            w = item.widget() if item is not None else None
            if w is None or w is self:
                continue
            geo = w.geometry()
            if geo.top() <= local.y() <= geo.bottom():
                target_index = i
                break

        if target_index is None:
            return

        cur_index = lay.indexOf(self)
        if cur_index < 0 or cur_index == target_index:
            return

        # QVBoxLayout 没有 moveItem，只能 takeAt + insertWidget。
        # 重新插入会把控件从当前槽位摘下来再放到新槽位，
        # 布局随即重排，视觉上就是「它被拖到了那一格」。
        item = lay.takeAt(cur_index)
        if item is not None:
            # 末尾有个 stretch，插入位置要留在它前面
            insert_at = target_index if target_index <= cur_index else target_index
            lay.insertWidget(insert_at, self)

    def current_position(self) -> int:
        """这一行此刻在布局里的序号（从 1 开始）。"""
        parent = self.parentWidget()
        lay = parent.layout() if parent is not None else None
        if lay is None:
            return self._index
        idx = lay.indexOf(self)
        return idx + 1 if idx >= 0 else self._index

class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        # 可写数据目录：源码运行时是 Anigame-script-manager/，
        # 打包后是 exe 所在目录（config.json、logs 都落在这里）。
        self.base_dir = _data_dir()
        self.config_path = self.base_dir / "config.json"
        self.manager = ConfigManager(self.config_path)
        self.config: AppConfig = self.manager.load()

        # 主题：没装素材就退回「简约」。
        # 昔涟系主题全靠她的美术图撑观感，仓库不带图，
        # 别人 clone 下来用 cyrene 会看到满屏空白。
        from ui.paths import has_cyrene_assets

        self._has_assets = has_cyrene_assets()
        wanted = getattr(self.config, "theme", "") or theme_mod.DEFAULT_THEME
        self.theme = theme_mod.resolve_for_assets(wanted, self._has_assets)

        self.worker: ScriptRunnerWorker | None = None
        self.worker_thread: QThread | None = None
        self._rows: list[TaskRow] = []
        self._elapsed = 0

        self.setWindowTitle(f"{APP_NAME} · 涟漪")
        self.resize(1120, 720)

        # 去掉系统标题栏，整窗自绘。
        #
        # 系统标题栏是白底（Win10/11 都是），压在深色界面上会留一条
        # 割裂的白带。要去掉它就得自己实现拖动、缩放和三个控制按钮——
        # 这些都在 ui/frameless.py 里，这里只负责开启。
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window
        )
        # 半透明背景：圆角之外要透出桌面，否则四个角会是黑色方块。
        # 背景本身由 WindowBackdrop 画（含圆角裁切）。
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)
        self._frame = FramelessHelper(self)
        # 内容区四边留一点缝，不然贴边拖拽的手感很怪
        self.setContentsMargins(0, 0, 0, 0)

        self._set_app_icon()
        self._build()
        self.apply_theme()

        # 最大化 / 还原时通知背景层切换圆角，否则贴屏会露出四角缝隙
        self._sync_corner_mode()
        QTimer.singleShot(120, self.refresh_status)
        QTimer.singleShot(1200, self.check_updates)

    def _sync_corner_mode(self) -> None:
        """让背景层和 DWM 都切换到「圆角 / 直角」。"""
        if hasattr(self, "backdrop"):
            self.backdrop._square_corners = self.isMaximized()
        self._apply_window_mask()

    def _apply_window_mask(self) -> None:
        """把窗口外形通知给系统。

        优先用 DWM 原生圆角（Win11）：抗锯齿由系统完成，
        效果和普通系统窗口一致。

        不用 setMask(QRegion)：遮罩是位图级的，边缘没有抗锯齿，
        12px 半径下锯齿明显（用户实测「锯齿状严重」）。
        Win10 不支持 DWM 圆角时，退回直角——宁可没有圆角，
        也不用带锯齿的遮罩。
        """
        from PySide6.QtGui import QRegion
        from ui.dwm import apply_round_corners, supports_dwm_rounding

        rounded = not self.isMaximized() and supports_dwm_rounding()
        hwnd = int(self.winId())
        ok = apply_round_corners(hwnd, rounded)

        # 无论 DWM 是否成功都清掉遮罩：
        # 有 DWM 时遮罩反而多余（还带锯齿）；没 DWM 时也要直角。
        self.clearMask()

    def changeEvent(self, event) -> None:  # noqa: N802
        # 最大化状态变化时 Qt 会发 WindowStateChange
        if event.type() == event.Type.WindowStateChange:
            self._sync_corner_mode()
        super().changeEvent(event)

    def _set_app_icon(self) -> None:
        """窗口和任务栏图标。

        优先用 app-icon.ico（星魂4 生成的多尺寸图标，跟 exe 上那个一致）。
        以前这里用的是 ripples.ico（她眼睛的特写），跟 exe 图标不是同一张，
        任务栏和窗口标题栏会显示成两个不同的图。
        """
        from PySide6.QtGui import QIcon

        for name in ("app-icon.ico", "ripples.ico", "p-icon.png"):
            p = _asset("cyrene", "加工", name)
            if p.exists():
                self.setWindowIcon(QIcon(str(p)))
                return

    # ---- 骨架 ----
    def _build(self) -> None:
        root = QWidget()
        root.setObjectName("Root")
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        outer.addWidget(self._build_titlebar())

        # 更新提示条：默认隐藏，只有确实有新版本才出现
        self.update_banner = QWidget()
        self.update_banner.setObjectName("UpdateBanner")
        banner_lay = QHBoxLayout(self.update_banner)
        banner_lay.setContentsMargins(18, 8, 14, 8)
        banner_lay.setSpacing(10)
        self.update_label = QLabel("")
        self.update_label.setObjectName("UpdateLabel")
        self.update_label.setWordWrap(True)
        banner_lay.addWidget(self.update_label, 1)
        close_btn = QPushButton("关闭")
        close_btn.setObjectName("RowButton")
        close_btn.clicked.connect(lambda: self.update_banner.setVisible(False))
        banner_lay.addWidget(close_btn)
        self.update_banner.setVisible(False)
        outer.addWidget(self.update_banner)

        # 主体分两层：
        #   page_stack 里是「整宽页面」——设置、画廊，它们不需要侧栏；
        #   队列页单独一套布局（侧栏 + 队列），因为它要显示今日状态。
        #
        # 为什么这样拆：设置页和画廊页原来被塞在「侧栏右侧」那一小块里，
        # 左边永远留着一条「今日状态」，页面本身只有窗口三分之二的宽度。
        # 那两页根本不需要状态栏，占着位置纯属浪费。
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self.page_stack = QStackedWidget()
        self.page_stack.setObjectName("PageStack")

        # 0 队列：侧栏 + 队列（内部再切队列本体）
        queue_page = QWidget()
        queue_page.setObjectName("Root")
        queue_lay = QHBoxLayout(queue_page)
        queue_lay.setContentsMargins(0, 0, 0, 0)
        queue_lay.setSpacing(0)
        queue_lay.addWidget(self._build_side(), 0)
        queue_lay.addWidget(self._build_center(), 1)
        self.page_stack.addWidget(queue_page)

        # 1 设置：整宽
        self._settings_view = self._build_settings_view()
        self.page_stack.addWidget(self._settings_view)

        # 2 画廊：整宽
        self._gallery_view = self._build_gallery_view()
        self.page_stack.addWidget(self._gallery_view)

        body.addWidget(self.page_stack, 1)
        outer.addLayout(body, 1)

        outer.addWidget(self._build_footer())
        self.setCentralWidget(root)

        # 整窗背景：铺满 root 的最底层，所有子控件都压在它上面。
        # 必须在 setCentralWidget 之后创建，否则它会被 root 的布局挤走。
        self.backdrop = WindowBackdrop(self.theme, root)
        self.backdrop.setGeometry(0, 0, root.width(), root.height())
        self.backdrop.lower()

        # root 尺寸变化时把背景层拉满。
        # 用 resizeEvent 而不是布局，是因为它要盖在所有子控件下面当背景，
        # 交给布局会占掉一行空间。
        _prev_resize = root.resizeEvent

        def _fit_backdrop(event) -> None:
            self.backdrop.setGeometry(0, 0, root.width(), root.height())
            self.backdrop.lower()
            if _prev_resize is not None:
                _prev_resize(event)

        root.resizeEvent = _fit_backdrop  # type: ignore[method-assign]

    def _titlebar_icon(self, size: int):
        """标题栏左边那个小图标。

        直接从 app-icon.ico 取 —— 它是 tools/make_icon_ps.py 生成的，
        已经抠好边、留好白、含完整尺寸。这里只负责缩放到需要的像素，
        不做任何裁切或加框。
        """
        from PySide6.QtGui import QIcon

        p = _asset("cyrene", "加工", "app-icon.ico")
        if not p.exists():
            return None
        icon = QIcon(str(p))
        if icon.isNull():
            return None
        return icon.pixmap(size, size)

    def _build_titlebar(self) -> QWidget:
        bar = TitleBar(self.theme)
        # 76：应用图标 38，右侧两行台词同为 15px，行距加起来约 42px。
        bar.setFixedHeight(76)

        # 标题栏整体可以拖动移动窗口（无边框之后必须自己实现）。
        # 按钮和输入控件会各自吃掉鼠标事件，所以拖动手感只在空白处生效。
        self._frame.bind_drag_area(bar)

        lay = QHBoxLayout(bar)
        lay.setContentsMargins(18, 0, 16, 0)
        lay.setSpacing(9)

        # 应用图标：直接用 app-icon.ico。
        #
        # 以前这里是「读原图 → 按包围盒取正方形 → 圆角裁切 → 加描边」，
        # 那是原图带深蓝底时的补救。现在图已经用 PS 抠干净了（带真实 alpha），
        # 再套一层圆角等于给它强行加了个方框，反而难看。
        # ico 本身已经排好留白（FILL_RATIO），按高度缩放即可。
        icon_pm = self._titlebar_icon(38) if self._has_assets else None
        if icon_pm is not None:
            icon = QLabel()
            icon.setObjectName("AppIcon")
            icon.setFixedSize(38, 38)
            icon.setStyleSheet("background: transparent;")
            icon.setPixmap(icon_pm)
            lay.addWidget(icon)
        # 没有图标时不在这里补文字——下面的品牌区本来就会显示名字，
        # 两处都显示会变成「Ripple Ripple · 涟漪」。

        # 品牌：官方的心形手写 logo（已裁掉透明留白）。
        logo_shown = False
        for logo_path in (
            _asset("cyrene", "加工", "logo-trim.png"),
            _asset("cyrene", "原图", "logo-official.png"),
        ) if self._has_assets else ():
            if not logo_path.exists():
                continue
            pm = QPixmap(str(logo_path))
            if pm.isNull():
                continue
            lg = pm.scaledToHeight(28, Qt.TransformationMode.SmoothTransformation)
            logo = QLabel()
            logo.setPixmap(lg)
            logo.setFixedSize(lg.size())
            logo.setStyleSheet("background: transparent;")
            lay.addWidget(logo)
            logo_shown = True
            break

        if not logo_shown:
            # 品牌区：英文名 + 「· 涟漪」。
            # 软件名是英文，但界面里的中文副名保留——用户只要求改软件名。
            en = QLabel(APP_EN)
            en.setObjectName("BrandEn")
            lay.addWidget(en)

            dot = QLabel("·")
            dot.setObjectName("BrandDot")
            lay.addWidget(dot)

            cn = QLabel("涟漪")
            cn.setObjectName("BrandCn")
            lay.addWidget(cn)

        # 标题栏那句关于「笑容」的话，原句来自 3.7 主线：
        #   就算世界并不温柔，那也没有关系。只要我不曾忘记，就永远有人记得「笑容」的意义。
        #
        # 这是**一句话**，不是两句。之前拆成两个 QLabel 上下排，
        # 结果行距由两个独立控件的高度决定，看起来像两段无关的话。
        # 现在改成一个 QLabel + 固定换行位置，行距由同一段文字的行距控制，
        # 读起来才是「它在那一行折下去了」而不是「换了一段」。
        #
        # 字体是行楷（见 theme.py 的 CyreneQuote），这句是她说的话，
        # 用印刷体就像一句系统提示了。
        quote = QLabel(
            "就算世界并不温柔，那也没有关系。\n"
            "只要我不曾忘记，就永远有人记得「笑容」的意义。"
        )
        quote.setObjectName("CyreneQuote")
        quote.setTextFormat(Qt.TextFormat.PlainText)
        quote.setContentsMargins(12, 0, 0, 0)
        lay.addWidget(quote)

        lay.addStretch(1)

        self.theme_button = QPushButton(self.theme.name)
        self.theme_button.setObjectName("Ghost")
        self.theme_button.clicked.connect(self.cycle_theme)
        lay.addWidget(self.theme_button)

        self.update_button = QPushButton("检查更新")
        self.update_button.setObjectName("Ghost")
        self.update_button.clicked.connect(self.check_updates)
        lay.addWidget(self.update_button)

        self.log_button = QPushButton("日志")
        self.log_button.setObjectName("Ghost")
        self.log_button.clicked.connect(self.toggle_log)
        lay.addWidget(self.log_button)

        # 美图按钮：放在「日志」右边、窗口按钮左边。
        #
        # 位置考虑：它是个「想看她了才点」的功能，不属于日常操作，
        # 所以不该占用底栏或中栏的显眼位置；但又要随手够得到，
        # 所以放在标题栏右侧这排轻量按钮里。
        # 没有素材时（仓库不带图的版本）不显示 —— 点开是空的反而奇怪。
        self.gallery_button = QPushButton("画廊")
        self.gallery_button.setObjectName("Ghost")
        self.gallery_button.setToolTip("看看昔涟")
        self.gallery_button.clicked.connect(self.open_gallery)
        self.gallery_button.setVisible(self._has_assets)
        lay.addWidget(self.gallery_button)

        # 应用设置：全局项（画廊目录这类）。
        # 和每一行任务自己的「设置」不同，这个管整个程序。
        self.settings_button = QPushButton("设置")
        self.settings_button.setObjectName("Ghost")
        self.settings_button.setToolTip("应用设置：画廊目录、超时截图…")
        self.settings_button.clicked.connect(self.open_app_settings)
        lay.addWidget(self.settings_button)

        # 自绘的窗口控制按钮。无边框之后系统不再提供这三个，
        # 得自己画、自己接事件。放在最右，宽度和系统标题栏按钮一致（46px）。
        lay.addSpacing(10)

        btn_box = QHBoxLayout()
        btn_box.setContentsMargins(0, 0, 0, 0)
        btn_box.setSpacing(0)

        self._btn_min = WindowButton(WindowButton.MINIMIZE)
        self._btn_min.mousePressEvent = lambda e: self.showMinimized()  # type: ignore[method-assign]
        btn_box.addWidget(self._btn_min)

        self._btn_max = WindowButton(WindowButton.MAXIMIZE)
        self._btn_max.mousePressEvent = lambda e: self._toggle_maximize()  # type: ignore[method-assign]
        btn_box.addWidget(self._btn_max)

        self._btn_close = WindowButton(WindowButton.CLOSE)
        self._btn_close.mousePressEvent = lambda e: self.close()  # type: ignore[method-assign]
        btn_box.addWidget(self._btn_close)

        btn_wrap = QWidget()
        btn_wrap.setObjectName("WindowButtons")
        btn_wrap.setLayout(btn_box)
        # 按钮组成一个整体塞进标题栏右侧，垂直贴顶
        lay.addWidget(btn_wrap, alignment=Qt.AlignmentFlag.AlignTop)

        return bar

    # ---- 页面切换 ----
    def show_queue(self) -> None:
        self.page_stack.setCurrentIndex(0)

    def show_settings(self) -> None:
        # 每次切进来都刷新一下统计，避免显示的是上次的旧路径
        self._refresh_settings_view()
        self.page_stack.setCurrentIndex(1)

    def show_gallery(self) -> None:
        self._refresh_gallery_view()
        self.page_stack.setCurrentIndex(2)

    def _build_settings_view(self) -> QWidget:
        """设置页。内容和 AppSettingsDialog 一样，但嵌在窗口里而不是弹窗。

        为什么改成页内：弹窗会遮住底栏的「开始执行」，
        而且看完设置想回队列得先关窗。切成页面后点一下就行。
        """
        wrap = QWidget()
        wrap.setObjectName("Root")
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(20, 16, 20, 12)
        lay.setSpacing(12)

        head = QHBoxLayout()
        title = QLabel("设置")
        title.setObjectName("SectionTitle")
        head.addWidget(title)
        head.addStretch(1)
        back = QPushButton("返回队列")
        back.setObjectName("Ghost")
        back.clicked.connect(self.show_queue)
        head.addWidget(back)
        lay.addLayout(head)

        form = QVBoxLayout()
        form.setSpacing(8)
        form.setContentsMargins(16, 14, 16, 14)

        form.addWidget(self._group_label("画廊"))
        hint = QLabel("「画廊」页从这个目录读图。留空则用程序旁的 Cyrene 文件夹。")
        hint.setObjectName("SectionHint")
        hint.setWordWrap(True)
        form.addWidget(hint)

        dir_row = QHBoxLayout()
        dir_row.setSpacing(6)
        self.gallery_edit = QLineEdit()
        self.gallery_edit.setPlaceholderText("留空 = 程序旁的 Cyrene 文件夹")
        self.gallery_edit.textChanged.connect(self._on_gallery_dir_changed)
        dir_row.addWidget(self.gallery_edit, 1)

        browse = QPushButton("浏览…")
        browse.setObjectName("Ghost")
        browse.clicked.connect(self._browse_gallery_dir)
        dir_row.addWidget(browse)

        reset = QPushButton("恢复默认")
        reset.setObjectName("Ghost")
        reset.clicked.connect(lambda: self.gallery_edit.setText(""))
        dir_row.addWidget(reset)

        dir_wrap = QWidget()
        dir_wrap.setLayout(dir_row)
        form.addWidget(dir_wrap)

        self.gallery_info = QLabel("")
        self.gallery_info.setObjectName("SectionHint")
        self.gallery_info.setWordWrap(True)
        form.addWidget(self.gallery_info)

        form.addSpacing(10)
        form.addWidget(self._group_label("其他"))
        self.screenshot_cb = QCheckBox("超时处理时保存现场截图")
        self.screenshot_cb.setToolTip("任务超时或卡住时截一张屏，存到 logs/screenshots/")
        form.addWidget(self.screenshot_cb)

        # 设置内容装进一张卡片里。
        # 直接摆在背景图上会和她的画打架——输入框、说明文字都看不清。
        card = QFrame()
        card.setObjectName("SettingsCard")
        card.setLayout(form)
        # 让卡片吃掉整行宽度（不加 maximumWidth）。
        # 之前设了 720 结果被压成一小块，说明文字折行折得很难看。
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        lay.addWidget(card)
        lay.addStretch(1)
        return wrap

    def _build_gallery_view(self) -> QWidget:
        """画廊页。网格直接在页内铺开，不是弹窗。"""
        from ui.gallery import GalleryGrid

        wrap = QWidget()
        wrap.setObjectName("Root")
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(20, 16, 20, 12)
        lay.setSpacing(12)

        head = QHBoxLayout()
        title = QLabel("画廊")
        title.setObjectName("SectionTitle")
        head.addWidget(title)
        self.gallery_count = QLabel("")
        self.gallery_count.setObjectName("SectionHint")
        head.addWidget(self.gallery_count)
        head.addStretch(1)
        back = QPushButton("返回队列")
        back.setObjectName("Ghost")
        back.clicked.connect(self.show_queue)
        head.addWidget(back)
        lay.addLayout(head)

        self._gallery_grid = GalleryGrid(self.theme, wrap)
        lay.addWidget(self._gallery_grid, 1)
        return wrap

    @staticmethod
    def _group_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("SideHeading")
        return lbl

    def _on_gallery_dir_changed(self, text: str) -> None:
        """路径一改就存盘，并刷新下面的统计。不用点保存。"""
        self.config.gallery_dir = text.strip()
        self.manager.save(self.config)
        self._update_gallery_info()

    def _refresh_settings_view(self) -> None:
        # 切回设置页时同步一次当前配置（可能被别处改过）
        self.gallery_edit.blockSignals(True)
        self.gallery_edit.setText(self.config.gallery_dir)
        self.gallery_edit.blockSignals(False)
        self.screenshot_cb.setChecked(self.config.enable_timeout_screenshot)
        self.screenshot_cb.toggled.connect(self._on_screenshot_toggled)
        self._update_gallery_info()

    def _on_screenshot_toggled(self, checked: bool) -> None:
        self.config.enable_timeout_screenshot = checked
        self.manager.save(self.config)

    def _update_gallery_info(self) -> None:
        from ui.gallery import EXTS, gallery_dir

        custom = self.gallery_edit.text().strip()
        target = gallery_dir(custom)
        if not target.is_dir():
            self.gallery_info.setText(f"目录不存在：{target}")
            return
        try:
            count = sum(1 for p in target.iterdir() if p.is_file() and p.suffix.lower() in EXTS)
        except OSError as exc:
            self.gallery_info.setText(f"读不了这个目录：{exc}")
            return
        suffix = "" if custom else "（默认位置）"
        self.gallery_info.setText(f"{target}{suffix} — {count} 张图")

    def _browse_gallery_dir(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        current = self.gallery_edit.text().strip()
        start = current if (current and Path(current).is_dir()) else str(Path.home())
        path = QFileDialog.getExistingDirectory(self, "选择图片目录", start)
        if path:
            self.gallery_edit.setText(path)

    def _refresh_gallery_view(self) -> None:
        from ui.gallery import gallery_dir

        self._gallery_grid.reload(self.config.gallery_dir)
        count = self._gallery_grid.count()
        if count:
            self.gallery_count.setText(f"{count} 张")
        else:
            target = gallery_dir(self.config.gallery_dir)
            self.gallery_count.setText(f"没找到图片（{target}）")

    def open_gallery(self) -> None:
        """切到画廊页。"""
        self.show_gallery()

    def open_app_settings(self) -> None:
        """切到设置页。"""
        self.show_settings()

    def _toggle_maximize(self) -> None:
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    # ---- 窗口尺寸 ----
    #
    # 固定大小，不允许拖动边缘缩放。
    #
    # 之前实现了 8 个方向的边缘拖拽，但实测手感不好：无边框窗口的
    # 边缘判定只有 6px，很难抓准；而且界面本来就是按固定布局排的，
    # 拉宽只会让卡片之间空出一大片，拉窄则挤成一团。
    # 用户 2026-11-14 要求「不能自己拉长拉短」，直接去掉这段。
    #
    # 最大化 / 还原仍然保留（双击标题栏或点 □ 按钮）。

    def _build_side(self) -> QWidget:
        wrap = QWidget()
        # 不要在这里 setStyleSheet —— 父控件上的内联样式会级联覆盖子控件，
        # 导致 GameCard 自己的 QSS 背景色失效（深色主题下卡片变白就是这原因）。
        # 背景色统一由 theme.stylesheet 里的 QWidget#SideWrap 负责。
        wrap.setObjectName("SideWrap")
        # 2026-11-09：248 → 286。
        # 248 时「理智 52/360」这种名字+数值挤在一行会换行，
        # 而且「每日任务 100/100」放不下要折行，卡片高度不可控。
        # 宽一点之后一行放得下，卡片反而更矮，一屏能装下四个游戏。
        wrap.setFixedWidth(286)
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(14, 16, 12, 14)
        lay.setSpacing(10)

        head = QLabel("今日状态")
        head.setObjectName("SideHeading")
        lay.addWidget(head)

        scroll = QScrollArea()
        scroll.setObjectName("SideScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        inner.setObjectName("SideInner")
        self.side_layout = QVBoxLayout(inner)
        self.side_layout.setContentsMargins(0, 0, 4, 0)
        self.side_layout.setSpacing(8)
        # 不给 stretch。以前这里有个 addStretch(1)，它会和卡片抢纵向空间，
        # 结果卡片被压到最小高度以下、文字互相叠住。
        # 现在卡片按自身需要的高度排，排不下时由滚动区负责滚。
        self.side_layout.setSizeConstraint(QVBoxLayout.SizeConstraint.SetMinimumSize)
        scroll.setWidget(inner)
        lay.addWidget(scroll, 1)

        self.refresh_button = QPushButton("刷新状态")
        self.refresh_button.setObjectName("Ghost")
        self.refresh_button.clicked.connect(self.refresh_status)
        lay.addWidget(self.refresh_button)

        # 星魂3 立绘和签名都去掉了。
        #
        # 原因：她已经在整窗背景里（art-reading 那张），
        # 左栏再放一张就是同一幅画看两遍，而且占掉最宝贵的一屏高度——
        # 侧栏本来就装不下四张状态卡，它俩让「明日方舟」被切掉半截。
        # 签名在标题栏的 logo 旁边已经出现过，这里重复了。
        return wrap

    def _build_center(self) -> QWidget:
        wrap = QWidget()
        wrap.setObjectName("Root")
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(20, 16, 20, 12)
        lay.setSpacing(12)

        head = QHBoxLayout()
        title = QLabel("执行队列")
        title.setObjectName("SectionTitle")
        head.addWidget(title)
        self.count_label = QLabel("")
        self.count_label.setObjectName("SectionHint")
        head.addWidget(self.count_label)
        head.addStretch(1)

        # 新建任务：以后加新游戏（比如新的自动化工具）不用去改 config.json。
        self.add_button = QPushButton("+ 新建任务")
        self.add_button.setObjectName("RowButton")
        self.add_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_button.setToolTip("添加一个新任务，在设置里填程序路径和参数")
        self.add_button.clicked.connect(self.add_task)
        head.addWidget(self.add_button)

        hint = QLabel("拖动左侧把手可调整顺序")
        hint.setObjectName("SectionHint")
        head.addWidget(hint)
        lay.addLayout(head)

        scroll = QScrollArea()
        scroll.setObjectName("QueueScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        # 不要在这里 setStyleSheet("background: transparent")：
        # QSS 会级联到所有子控件，把 TaskRow 自己的白底也覆盖成透明。
        # 这正是交接文档坑 #4 记录过的问题。改用 objectName + 全局 QSS。
        inner = QWidget()
        inner.setObjectName("QueueInner")
        self.queue_layout = QVBoxLayout(inner)
        self.queue_layout.setContentsMargins(0, 0, 6, 0)
        # 行间距收窄：原来 8px，五行加起来的空隙快有一行高了
        self.queue_layout.setSpacing(5)
        self.queue_layout.addStretch(1)
        scroll.setWidget(inner)
        lay.addWidget(scroll, 1)

        # 背景层：涟漪在最下面，水印叠在它上面，两者都在任务列表之下。
        self.halo = RippleHalo(self.theme, wrap)
        self.halo.lower()

        self.watermark = CyreneWatermark(self.theme, wrap)
        self.watermark.lower()
        self.watermark.stackUnder(scroll)

        # 中栏尺寸变化时把背景层拉满。不用布局管理器，是因为它们要盖在
        # 所有子控件下面当背景，交给布局反而会挤占任务列表的空间。
        def _fit_bg(_event=None) -> None:
            self.halo.setGeometry(0, 0, wrap.width(), wrap.height())
            self.watermark.setGeometry(0, 0, wrap.width(), wrap.height())
            self.halo.lower()
            self.watermark.raise_()
            self.watermark.stackUnder(scroll)

        wrap.resizeEvent = _fit_bg  # type: ignore[method-assign]

        self.log_view = QPlainTextEdit()
        self.log_view.setObjectName("LogView")
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(2000)
        self.log_view.setVisible(False)
        self.log_view.setFixedHeight(150)
        lay.addWidget(self.log_view)

        self._rebuild_queue()
        return wrap

    def _build_footer(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("Footer")
        bar.setFixedHeight(58)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(20, 0, 20, 0)
        lay.setSpacing(9)

        self.start_button = QPushButton("开始执行")
        self.start_button.setObjectName("Primary")
        self.start_button.clicked.connect(self.start_run)
        lay.addWidget(self.start_button)

        self.pause_button = QPushButton("暂停")
        self.pause_button.clicked.connect(self.toggle_pause)
        self.pause_button.setEnabled(False)
        lay.addWidget(self.pause_button)

        self.stop_button = QPushButton("停止")
        self.stop_button.setObjectName("Ghost")
        self.stop_button.clicked.connect(self.stop_run)
        self.stop_button.setEnabled(False)
        lay.addWidget(self.stop_button)

        # 结束后操作：位于「停止」右侧并以分隔线隔开。
        # 它属于「任务结束后的后续行为」而非「运行控制」，
        # 因此不与应用开始/暂停/停止控件相邻。
        # 点击展开多选面板（锁屏/睡眠/休眠/关机/关闭工具/退出模拟器），
        # 而非单一开关——各项影响程度差异大，合并会迫使二选一。
        sep = QLabel("·")
        sep.setObjectName("FooterStatus")
        lay.addWidget(sep)

        self.after_done_btn = QPushButton(self._after_done_text())
        self.after_done_btn.setObjectName("Ghost")
        self.after_done_btn.setToolTip("设置队列结束后执行的操作")
        self.after_done_btn.clicked.connect(self.open_after_done)
        lay.addWidget(self.after_done_btn)

        lay.addStretch(1)
        self.status_label = QLabel("待执行")
        self.status_label.setObjectName("FooterStatus")
        lay.addWidget(self.status_label)
        return bar

    def _after_done_text(self) -> str:
        """底栏按钮上显示当前启用了哪些「结束后操作」。"""
        cfg = self.config
        marks: list[str] = []
        if cfg.after_done_close_game:
            marks.append("关闭星铁")
        if cfg.after_done_close_emulator:
            marks.append("退出模拟器")
        if cfg.after_done_close_tools:
            marks.append("关闭工具")
        if cfg.after_done_lock:
            marks.append("锁屏")
        if cfg.after_done_sleep:
            marks.append("睡眠")
        if cfg.after_done_hibernate:
            marks.append("休眠")
        if cfg.shutdown_after_done:
            marks.append("关机")
        if not marks:
            return "结束后：无操作"
        if len(marks) == 1:
            return f"结束后：{marks[0]}"
        return f"结束后：{marks[0]} 等 {len(marks)} 项"

    def open_after_done(self) -> None:
        from ui.after_done import AfterDoneDialog

        dlg = AfterDoneDialog(self.config, self.theme, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        dlg.apply_to(self.config)
        self.manager.save(self.config)
        self.after_done_btn.setText(self._after_done_text())
        self._say(f"结束后操作已更新：{self._after_done_text().replace('结束后：', '')}")

    # ---- 主题 ----
    def apply_theme(self) -> None:
        self.setStyleSheet(theme_mod.stylesheet(self.theme) + theme_mod.progress_stylesheet(self.theme))
        self.theme_button.setText(self.theme.name)
        # 涟漪和水印用的是主题色与背景，换主题时要跟着重画
        if hasattr(self, "halo"):
            self.halo.set_theme(self.theme)
        if hasattr(self, "watermark"):
            self.watermark.set_theme(self.theme)

    def cycle_theme(self) -> None:
        """切换主题。

        没装素材时只保留「简约」一套——其余三套都依赖昔涟的美术图，
        切过去就是一屏空白，不如直接不给切。
        """
        if self._has_assets:
            keys = list(theme_mod.THEMES.keys())
        else:
            keys = [theme_mod.PLAIN.key]
            self._say("未检测到昔涟素材，仅提供「简约」主题")
        try:
            i = keys.index(self.theme.key)
        except ValueError:
            i = 0
        self.theme = theme_mod.THEMES[keys[(i + 1) % len(keys)]]
        self.config.theme = self.theme.key
        self.manager.save(self.config)
        self.apply_theme()
        self._rebuild_side(self._last_statuses)

    # ---- 队列 ----
    def add_task(self) -> None:
        """新建一个任务。

        为什么不直接加空行：空行的「程序」一栏是空的，用户得自己点设置
        找文件。这里先弹一次文件选择，选完再进详细设置，
        新任务立刻就是可用的状态。
        """
        from PySide6.QtWidgets import QFileDialog

        # 起始目录不写死盘符：从程序所在目录起，用户自己的工具放哪都行。
        # （以前这里写的是 A:\，那只是某台机器上的习惯。）
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择要加入队列的程序",
            str(_data_dir()),
            "程序 (*.exe *.bat *.cmd);;所有文件 (*.*)",
        )
        if not path:
            return

        task = TaskConfig(
            enabled=True,
            name=Path(path).stem,
            script_path=path,
            order=len(self.config.tasks) + 1,
        )
        self.config.tasks.append(task)

        # 选完文件直接进设置，让用户顺手把参数、超时一次配好
        from ui.task_settings import TaskSettingsDialog

        dlg = TaskSettingsDialog(task, self.theme, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            dlg.apply_to(task)
            if not task.name.strip():
                task.name = Path(path).stem

        self.manager.save(self.config)
        self._rebuild_queue()
        self._say(f"已添加任务：{task.name}")

    def delete_task(self, index: int) -> None:
        """删除一个任务。会先确认一次，因为它直接从配置里消失。"""
        tasks = self.config.tasks
        if not (1 <= index <= len(tasks)):
            return
        task = tasks[index - 1]
        reply = QMessageBox.question(
            self,
            APP_NAME,
            f"确定删除「{task.name}」吗？\n\n这个操作只移除队列里的这一项，不会卸载或删除程序本身。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        tasks.pop(index - 1)
        for i, t in enumerate(tasks, start=1):
            t.order = i
        self.manager.save(self.config)
        self._rebuild_queue()
        self._say(f"已删除任务：{task.name}")

    def _rebuild_queue(self) -> None:
        while self.queue_layout.count() > 1:
            item = self.queue_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._rows = []
        tasks = self.config.tasks
        for i, task in enumerate(tasks, start=1):
            row = TaskRow(task, i)
            row.moved.connect(self.move_task)
            row.toggled.connect(self.toggle_task)
            row.background_toggled.connect(self.toggle_background)
            row.timeout_edit_requested.connect(self.edit_timeout)
            row.settings_requested.connect(self.open_task_settings)
            row.delete_requested.connect(self.delete_task)
            self.queue_layout.insertWidget(self.queue_layout.count() - 1, row)
            self._rows.append(row)
        enabled = sum(1 for t in tasks if t.enabled)
        self.count_label.setText(f"{enabled} 项启用 · 共 {len(tasks)} 项")

    def move_task(self, src: int, dst: int) -> None:
        """拖动结束后把「界面上的顺序」写回配置。

        拖动过程中已经用 layout 实时换位了，所以这里**不能**再按
        src/dst 去动 config.tasks —— 那样会和界面上的实际顺序对不上。
        正确做法是：按 layout 里的真实顺序，把每一行对应的任务重新排。

        src/dst 两个参数只为兼容信号签名保留，实际不用。
        """
        rows = [r for r in self._rows if r is not None]
        if not rows:
            return

        # 用 layout.indexOf 拿真实的当前顺序（不是创建时的顺序）
        lay = self.queue_layout
        rows.sort(key=lambda r: lay.indexOf(r))

        ordered = []
        for row in rows:
            idx = getattr(row, "_index", 0)
            if 1 <= idx <= len(self.config.tasks):
                ordered.append(self.config.tasks[idx - 1])

        # 万一有任务没被任何行认领（理论上不会），补在后面，别丢数据
        if len(ordered) != len(self.config.tasks):
            claimed = {id(t) for t in ordered}
            for t in self.config.tasks:
                if id(t) not in claimed:
                    ordered.append(t)

        # 顺序没变就只刷新显示（拖了两下又放回原处的情况）
        if all(self.config.tasks[i] is t for i, t in enumerate(ordered)):
            self._rebuild_queue()
            return

        self.config.tasks = ordered
        for i, t in enumerate(self.config.tasks, start=1):
            t.order = i
        self.manager.save(self.config)
        self._rebuild_queue()
        # 拖动排序不再弹「已调整顺序：xxx」。
        # 行跟着鼠标实时换位，用户已经看到了结果，
        # 再在底栏说一句是多余的噪声。

    def toggle_background(self, index: int) -> None:
        """切换「后台并行」。勾上后该任务启动完就轮到下一个，不等它结束。"""
        tasks = self.config.tasks
        if not (1 <= index <= len(tasks)):
            return
        task = tasks[index - 1]
        task.run_in_background = not task.run_in_background
        self.manager.save(self.config)
        self._rebuild_queue()
        if task.run_in_background:
            self._say(f"{task.name} 改为后台并行（启动后队列继续）")
        else:
            self._say(f"{task.name} 已改为串行（等待其结束）")

    def toggle_task(self, index: int) -> None:
        tasks = self.config.tasks
        if not (1 <= index <= len(tasks)):
            return
        task = tasks[index - 1]
        task.enabled = not task.enabled
        self.manager.save(self.config)
        self._rebuild_queue()
        self._say(f"{task.name} 已{'启用' if task.enabled else '停用'}")

    def edit_timeout(self, index: int) -> None:
        """修改单个任务的最大运行时间。填 0 表示不限制。"""
        tasks = self.config.tasks
        if not (1 <= index <= len(tasks)):
            return
        task = tasks[index - 1]

        value, ok = QInputDialog.getInt(
            self,
            "设置最大运行时间",
            f"{task.name}\n\n超过该时长仍未结束时，按「{task.timeout_action}」处理。\n"
            "填 0 表示不限制。",
            task.timeout_minutes,
            0,
            1440,
            5,
        )
        if not ok:
            return
        task.timeout_minutes = int(value)
        self.manager.save(self.config)
        self._rebuild_queue()
        self._say(f"{task.name} 的最大运行时间改为 {TaskRow._duration_text(task.timeout_minutes)}")

    def open_task_settings(self, index: int) -> None:
        """齿轮：打开这个任务的详细设置。"""
        tasks = self.config.tasks
        if not (1 <= index <= len(tasks)):
            return
        task = tasks[index - 1]

        from ui.task_settings import TaskSettingsDialog

        dlg = TaskSettingsDialog(task, self.theme, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        dlg.apply_to(task)
        self.manager.save(self.config)
        self._rebuild_queue()
        self._say(f"{task.name} 的设置已保存")

    # ---- 状态 ----
    _last_statuses: list[Any] = []

    def refresh_status(self) -> None:
        self.refresh_button.setEnabled(False)
        self.refresh_button.setText("读取中…")
        self._fetcher = StatusFetcher()
        self._fetcher.done.connect(self._on_status_done)
        self._fetcher.failed.connect(self._on_status_failed)
        threading.Thread(target=self._fetcher.run, daemon=True).start()

    def _on_status_done(self, statuses: list) -> None:
        self._last_statuses = statuses
        self._rebuild_side(statuses)
        self.refresh_button.setEnabled(True)
        self.refresh_button.setText("刷新状态")

    def _on_status_failed(self, message: str) -> None:
        self._rebuild_side([self._error_status(message)])
        self.refresh_button.setEnabled(True)
        self.refresh_button.setText("刷新状态")

    @staticmethod
    def _error_status(message: str):
        class _S:
            name = "状态读取失败"
            daily_done = None
            stamina = None
            stamina_max = None
            stamina_label = ""
            note = message
            error = ""
        return _S()

    def _rebuild_side(self, statuses: list) -> None:
        # 清空：现在布局里没有 stretch 了，全部清掉再重建
        while self.side_layout.count():
            item = self.side_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        if not statuses:
            empty = QLabel("尚未读取状态")
            empty.setObjectName("GameMeta")
            self.side_layout.addWidget(empty)
            return
        for st in statuses:
            card = GameCard(st, self.theme)
            self.side_layout.addWidget(card)

    # ---- 执行 ----
    def start_run(self) -> None:
        self.config = self.manager.load()
        # 只把启用中的任务交给执行器；self.config.tasks 保持完整，
        # 否则之后任何一次保存都会把停用的任务从 config.json 里抹掉。
        run_tasks = [t for t in self.config.tasks if t.enabled]
        if not run_tasks:
            QMessageBox.information(self, APP_NAME, "没有启用的任务。")
            return
        run_tasks.sort(key=lambda t: t.order)

        logger = FileLogger(self.base_dir / "logs")
        stats = RuntimeStatsManager(self.base_dir)
        self.worker = ScriptRunnerWorker(
            tasks=run_tasks,
            shutdown_after_done=self.config.shutdown_after_done,
            shutdown_delay_seconds=self.config.shutdown_delay_seconds,
            logger=logger,
            stats_manager=stats,
            enable_timeout_screenshot=self.config.enable_timeout_screenshot,
            after_done_actions={
                "lock": self.config.after_done_lock,
                "sleep": self.config.after_done_sleep,
                "hibernate": self.config.after_done_hibernate,
                "close_emulator": self.config.after_done_close_emulator,
                "close_tools": self.config.after_done_close_tools,
                "close_game": self.config.after_done_close_game,
            },
        )
        self.worker_thread = QThread(self)
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run)
        self.worker.log_signal.connect(self.append_log)
        self.worker.status_signal.connect(self.set_status)
        self.worker.task_started_signal.connect(self._on_task_started)
        self.worker.finished_signal.connect(self._on_finished)
        self.worker.shutdown_prompt_signal.connect(self._on_shutdown_prompt)
        self.worker_thread.start()

        self.start_button.setEnabled(False)
        self.pause_button.setEnabled(True)
        self.stop_button.setEnabled(True)
        self._say("运行中")

    def _on_task_started(self, name: str, index: int, total: int) -> None:
        for i, row in enumerate(self._rows, start=1):
            row.set_active(i == index)
        self._say(f"{index}/{total} · {name}")

    def toggle_pause(self) -> None:
        if not self.worker:
            return
        if self.pause_button.text() == "暂停":
            self.worker.request_pause()
            self.pause_button.setText("继续")
        else:
            self.worker.request_resume()
            self.pause_button.setText("暂停")

    def stop_run(self) -> None:
        if self.worker:
            self.worker.request_stop()

    def _on_finished(self, had_error: bool) -> None:
        if self.worker_thread:
            self.worker_thread.quit()
            self.worker_thread.wait(3000)
        self.worker = None
        self.worker_thread = None
        self.start_button.setEnabled(True)
        self.pause_button.setEnabled(False)
        self.pause_button.setText("暂停")
        self.stop_button.setEnabled(False)
        for row in self._rows:
            row.set_active(False)
        self._say("已完成（有异常）" if had_error else "已完成")

    def _on_shutdown_prompt(self, delay: int) -> None:
        """关机倒计时提示。

        重要：这里**不能用 box.exec()**。
        exec() 是模态阻塞的，人不在电脑前时它会一直挂着，
        而它挂在 UI 线程上——窗口不响应、日志不刷新，
        更糟的是它把一个「已经在倒计时」的系统关机伪装成「等你确认」。

        现在 shutdown /s /t N 已经在 core 里发出去了（Windows 自己在倒计时），
        这个窗口只负责「告诉用户 + 提供一个取消按钮」。
        用 show() 非阻塞，人不在也能到点关机。
        """
        box = QMessageBox(self)
        box.setWindowTitle(APP_NAME)
        box.setText(f"全部任务结束，{delay} 秒后关机。")
        box.setInformativeText("要取消就点下面那个按钮；不管它也会照常关机。")
        cancel = box.addButton("取消关机", QMessageBox.ButtonRole.RejectRole)
        box.addButton("关闭", QMessageBox.ButtonRole.AcceptRole)
        box.setModal(False)
        box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

        def _on_clicked(btn) -> None:
            if btn is cancel:
                import subprocess

                subprocess.run(["shutdown", "/a"], capture_output=True, check=False)
                self.append_log("已取消关机")
                self._say("已取消关机")

        box.buttonClicked.connect(_on_clicked)
        box.show()
        # 别让 box 被垃圾回收掉，否则窗口一闪就没了
        self._shutdown_box = box

    # ---- 更新检查 ----
    # 用户要求：只提醒，不下载、不启动任何软件。星铁暂时跳过。
    UPDATE_SKIP = {"m7a"}

    def check_updates(self) -> None:
        self.update_button.setEnabled(False)
        self.update_button.setText("检查中…")
        self._updater = UpdateFetcher(skip_keys=self.UPDATE_SKIP)
        self._updater.done.connect(self._on_updates_done)
        self._updater.failed.connect(self._on_updates_failed)
        threading.Thread(target=self._updater.run, daemon=True).start()

    def _on_updates_done(self, results: list) -> None:
        self.update_button.setEnabled(True)
        self.update_button.setText("检查更新")

        outdated = [r for r in results if r.status == "outdated"]
        unknown = [r for r in results if r.status in ("unknown", "missing")]

        if not outdated:
            tail = f"（{len(unknown)} 个无法判断）" if unknown else ""
            self.update_label.setText(f"都已是最新{tail}")
            self._show_banner(outdated=False)
            self.append_log(
                "更新检查：" + "；".join(
                    f"{r.tool.name} {r.local or '?'}"
                    + (f"→{r.latest}" if r.status == "outdated" else "")
                    for r in results
                )
            )
            return

        parts = [f"{r.tool.name} {r.local} → {r.latest}" for r in outdated]
        self.update_label.setText("有更新：" + "，" .join(parts) + "　（请自行更新，程序不会自动下载）")
        self._show_banner(outdated=True)
        self.append_log("更新检查：" + "；".join(parts))

    def _on_updates_failed(self, message: str) -> None:
        self.update_button.setEnabled(True)
        self.update_button.setText("检查更新")
        self.update_label.setText(f"检查更新失败：{message}")
        self._show_banner(outdated=False)
        self.append_log(f"更新检查失败：{message}")

    def _show_banner(self, outdated: bool) -> None:
        # 用 property + 全局 QSS，不要内联 setStyleSheet。
        # 原来这里是内联样式，背景写的是浅色 panel_2，
        # 在深色界面上像贴了张白纸，而且内联样式还会级联到子控件
        # （交接文档坑 #4，这已经是第三次踩了）。
        self.update_banner.setProperty("outdated", "true" if outdated else "false")
        for w in (self.update_banner, self.update_label):
            w.style().unpolish(w)
            w.style().polish(w)
        self.update_banner.setVisible(True)

    # ---- 杂项 ----
    def toggle_log(self) -> None:
        self.log_view.setVisible(not self.log_view.isVisible())

    def append_log(self, line: str) -> None:
        self.log_view.appendPlainText(line)

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def _say(self, text: str) -> None:
        self.status_label.setText(text)


def main() -> int:
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
