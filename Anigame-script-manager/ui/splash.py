# -*- coding: utf-8 -*-
"""启动画面：程序打开那一两秒看到的东西。

为什么要有它：主窗口一出来就是满屏数据，太快了，没有「开始」的感觉。
这张只停留很短时间，说一句她的话，然后让位给真正的工作界面。

设计上刻意保持极简 —— 立绘 + 一句台词 + 签名。
soul.md 写过不要堆意象，所以这里除了她本人和一行字，什么都没有。
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QWidget

from ui.fonts import brush_font
from ui.paths import asset as _asset

ASSETS = _asset("cyrene", "加工")


class Splash(QWidget):
    """无边框、半透明、居中的启动画面。

    窗口比例和壁纸保持一致（16:9），这样那张图能完整地露出来，
    不会被裁成竖条。文字放在左半边——她本人在画面右侧，
    左边是星空和光带，正好空着。
    """

    W, H = 960, 540

    # 四角圆角半径。18 在这个尺寸上几乎看不出来，调到 26 才有柔和的观感。
    # 主界面的窗口圆角用的是它自己那套，两边不共用常量——
    # 启动画面是无边框浮层，主界面是可放大的窗口，半径本来就该不同。
    CORNER = 26

    def __init__(self, theme=None):
        super().__init__()
        self._theme = theme
        self._bg = QColor("#FDF7FA")
        self._accent = QColor("#DF7BA0")
        self._muted = QColor("#9E7E8D")
        self._teal = QColor("#7FCFC9")

        if theme is not None:
            self._bg = QColor(theme.page)
            self._accent = QColor(theme.accent)
            self._muted = QColor(theme.muted)
            self._teal = QColor(theme.teal)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.SplashScreen
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.resize(self.W, self.H)
        self._center()

        self._pix: QPixmap | None = None
        for name in ("p-full.png", "p-half.png", "昔涟立绘.png"):
            p = ASSETS / name
            if p.exists():
                pm = QPixmap(str(p))
                if not pm.isNull():
                    self._pix = pm
                    break

        self._sig: QPixmap | None = None
        sp = ASSETS / "signature.png"
        if sp.exists():
            pm = QPixmap(str(sp))
            if not pm.isNull():
                self._sig = pm

        # 官方的心形手写 logo（用户提供）
        #
        # 原图 logo-official.png 是 335×303，但四周有大量透明留白：
        # 实际笔画只占 (3,80)-(257,230)，也就是 254×150。
        # 按整张图画的话，100px 看起来只有 76px，字会显得又小又飘。
        # 所以优先用裁掉留白的 logo-trim.png；没有裁切版再退回原图。
        self._logo: QPixmap | None = None
        for lp in (
            _asset("cyrene", "加工", "logo-trim.png"),
            _asset("cyrene", "原图", "logo-official.png"),
        ):
            if not lp.exists():
                continue
            pm = QPixmap(str(lp))
            if not pm.isNull():
                self._logo = pm
                break

        # 整窗背景：星空回眸那张壁纸。没有就退回白底卡片。
        self._wall: QPixmap | None = None
        wp = _asset("cyrene", "原图", "art-starry.jpg")
        if wp.exists():
            pm = QPixmap(str(wp))
            if not pm.isNull():
                self._wall = pm

        # 有壁纸时文字要反过来用浅色，否则深底深字看不见。
        # 这个判断必须放在加载壁纸之后。
        if self._wall is not None:
            self._text_main = QColor("#FFFFFF")
            self._text_dim = QColor(255, 255, 255, 190)
        else:
            self._text_main = self._accent
            self._text_dim = self._muted

    @staticmethod
    def _brush_font(size: int) -> QFont:
        """手写艺术字的字体。

        走 ui.fonts 统一解析：优先华文行楷（STXingkai），
        系统没有就退回楷体，再没有才用雅黑。
        以前这里自己写了一遍查找逻辑，和主界面各写各的，
        结果两边行为不一致——一处能出字一处出黑体。
        """
        return brush_font(size)

    def _center(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        self.move(
            geo.center().x() - self.W // 2,
            geo.center().y() - self.H // 2,
        )

    def paintEvent(self, event) -> None:  # noqa: N802
        w, h = self.width(), self.height()

        # 先画到一张独立的透明画布上，最后整体裁圆角再贴到控件。
        #
        # 为什么必须用独立画布：直接画在 QPainter(self) 上时，
        # 裁切要跟控件已有的背景合成，结果不可控。
        #
        # 为什么用 setClipPath 而不是 DestinationIn：
        # 实测 DestinationIn 在这里完全没效果（四角 alpha 仍然是 255），
        # 因为它要求源像素的 alpha 参与乘法，而 fillPath 用的纯色 alpha=255，
        # 乘完等于没裁。setClipPath 是在绘制时就丢掉路径外的像素，
        # 不依赖合成模式，验证过四角 alpha 确实是 0。
        canvas = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
        canvas.fill(Qt.GlobalColor.transparent)

        p = QPainter(canvas)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        # 整个绘制过程都在圆角路径内进行
        from PySide6.QtGui import QPainterPath

        clip = QPainterPath()
        clip.addRoundedRect(0, 0, w, h, self.CORNER, self.CORNER)
        p.setClipPath(clip)

        # ---- 底：星空壁纸铺满 ----
        #
        # 以前是白底圆角卡片。现在换成 art-starry.jpg 铺满整窗，
        # 上面压一层深的柔光，让粉色的字浮得出来。
        # 没有壁纸才退回纯色。
        if self._wall is not None:
            # KeepAspectRatioByExpanding + 居中：比例和窗口一致时正好铺满且不裁，
            # 比例不一致的图则保住整幅、只裁掉多出来的边。
            cover = self._wall.scaled(
                w, h,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            p.drawPixmap(
                (w - cover.width()) // 2,
                (h - cover.height()) // 2,
                cover,
            )
            # 压暗 + 柔光，保证文字可读。
            # 之前是径向遮罩、整体压到 alpha 175，把她原本的亮度也吃掉了。
            # 现在改成横向渐变：左边（文字区）压深一点，右边留亮，让她保持原有的通透。
            from PySide6.QtGui import QLinearGradient

            veil = QLinearGradient(0, 0, w, 0)
            veil.setColorAt(0.00, QColor(14, 9, 24, 185))
            veil.setColorAt(0.30, QColor(14, 9, 24, 130))
            veil.setColorAt(0.55, QColor(14, 9, 24, 40))
            veil.setColorAt(0.72, QColor(14, 9, 24, 0))
            veil.setColorAt(1.00, QColor(14, 9, 24, 0))
            p.fillRect(self.rect(), veil)
            # 底部再压一条，给细线和可能的落款留位置
            from PySide6.QtGui import QLinearGradient as _LG

            bottom = _LG(0, h, 0, int(h * 0.78))
            bottom.setColorAt(0.0, QColor(10, 6, 18, 120))
            bottom.setColorAt(1.0, QColor(10, 6, 18, 0))
            p.fillRect(self.rect(), bottom)
            # 圆角裁切放在 paintEvent 最末尾统一做（见方法结尾），
            # 这里不再单独裁一次 —— 只裁壁纸的话，后画的文字和 logo
            # 会盖到圆角外面去。
        else:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(self._bg)
            p.drawRoundedRect(0, 0, w, h, self.CORNER, self.CORNER)

        # 立绘只在没有壁纸时才画 —— 有壁纸的话她已经在画面里了
        if self._wall is None and self._pix is not None:
            target_h = int(h * 0.52)
            scaled = self._pix.scaledToHeight(
                target_h, Qt.TransformationMode.SmoothTransformation
            )
            x = (w - scaled.width()) // 2
            y = int(h * 0.035)
            p.setOpacity(0.96)
            p.drawPixmap(x, y, scaled)
            p.setOpacity(1.0)

        # 文字整组靠左排：右半边是她本人，左半边是星空和光带，本来就空着。
        # 面板取 46% 而不是 52%——台词第二行「自往昔投下，向未来送去涟漪」
        # 有 13 个字，面板再宽右侧就会爬到她的发带上。
        left_w = int(w * 0.46)
        left_cx = 26 + left_w // 2

        # 品牌：优先用官方的心形手写 logo；没有才退回纯文字。
        #
        # 这张是手绘签名图，不是字体 —— 所以「换个字体」对它没有意义。
        # logo-trim.png 已经裁掉了原图四周的透明留白（335×303 → 254×150），
        # 现在按 30% 窗宽画，笔画厚度才够，跟 11-07 那版观感对齐。
        if self._logo is not None:
            logo_w = int(w * 0.30)
            lg = self._logo.scaledToWidth(
                logo_w, Qt.TransformationMode.SmoothTransformation
            )
            logo_y = int(h * (0.13 if self._wall is not None else 0.18))
            logo_x = left_cx - lg.width() // 2

            # 签名本身是 rgb(240,144,208) 的亮粉，亮度 0.765 其实不低，
            # 但压在深蓝星空上会显得闷。先垫一层同色柔光把它托起来。
            if self._wall is not None:
                from PySide6.QtGui import QRadialGradient

                glow = QRadialGradient(
                    logo_x + lg.width() / 2,
                    logo_y + lg.height() / 2,
                    lg.width() * 0.60,
                )
                glow.setColorAt(0.0, QColor(240, 144, 208, 46))
                glow.setColorAt(1.0, QColor(240, 144, 208, 0))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(glow)
                p.drawEllipse(
                    int(logo_x + lg.width() / 2 - lg.width() * 0.60),
                    int(logo_y + lg.height() / 2 - lg.width() * 0.60),
                    int(lg.width() * 1.20),
                    int(lg.width() * 1.20),
                )

            p.drawPixmap(logo_x, logo_y, lg)
            text_top = logo_y + lg.height() + 18
        else:
            f_title = QFont("Microsoft YaHei UI", 26, QFont.Weight.Bold)
            p.setFont(f_title)
            p.setPen(self._text_main)
            p.drawText(
                0, int(h * 0.28), left_w, 42,
                Qt.AlignmentFlag.AlignHCenter, "Ripple",
            )
            text_top = int(h * 0.36)

        # 2026-11-10 用户要求删掉「涟漪」和「昔涟」两处文字。
        # 签名图 signature.png 画的就是「昔涟」两字，一并去掉。
        #
        # 台词位置也从「logo 正下方」改成「画面左下角」：
        # 原来贴在 logo 下面，整组文字挤在左上角，右下角空一大块。
        # 挪到左下之后文字沿着左侧往下排，和她站的位置（偏右）错开，
        # 画面重心才稳。
        #
        # 这句是「涟漪」这个名字的出处：
        #   希望文字像石子点水，自往昔投下，向未来送去涟漪。
        f_quote = self._brush_font(17)
        p.setFont(f_quote)
        p.setPen(self._text_dim)

        margin_x = 26
        quote_h = 30
        # 左下角：底部留出细线的位置（h*0.93），台词压在它上面
        quote_y = int(h * 0.93) - quote_h * 2 - 14
        p.drawText(
            margin_x, quote_y, left_w, quote_h,
            Qt.AlignmentFlag.AlignLeft,
            "希望文字像石子点水",
        )
        p.drawText(
            margin_x, quote_y + quote_h, left_w, quote_h,
            Qt.AlignmentFlag.AlignLeft,
            "自往昔投下，向未来送去涟漪",
        )

        # 底部一条渐变细线，粉到青。跟着台词一起靠左。
        from PySide6.QtGui import QLinearGradient

        line_y = int(h * 0.93)
        line_w = 120
        line_cx = margin_x + line_w // 2
        grad = QLinearGradient(margin_x, 0, margin_x + line_w, 0)
        grad.setColorAt(0.0, QColor(self._accent.red(), self._accent.green(), self._accent.blue(), 110))
        grad.setColorAt(1.0, QColor(self._teal.red(), self._teal.green(), self._teal.blue(), 110))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(grad)
        p.drawRoundedRect(margin_x, line_y, line_w, 2, 1, 1)

        p.end()

        # 圆角已经在开头用 setClipPath 裁好了，这里只把结果贴到控件上。
        painter = QPainter(self)
        painter.drawImage(0, 0, canvas)
        painter.end()
