# -*- coding: utf-8 -*-
"""Ripples · 涟漪 —— 主题定义。

一套 token 驱动整个界面。设计稿见 docs/ripples-theme-preview.html。

昔涟是默认主题：粉白打底，桃色点睛。粉只出现在「该被看见」的
位置（主按钮、进行中的卡片、进度条、品牌字），状态色保持独立语义，
不让粉把「已清/未清」盖住。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    """一个主题的全部颜色与排版 token。"""

    key: str
    name: str
    # 底层
    page: str          # 窗口底色
    panel: str         # 卡片、侧栏
    panel_2: str       # 卡片内嵌层、次级按钮
    border: str        # 描边
    # 文字
    text: str          # 主文字
    muted: str         # 次要文字
    # 强调
    accent: str
    accent_fg: str     # accent 上的文字色
    accent_soft: str   # 强调色的浅色版，用于渐变尾巴
    # 语义
    ok: str
    ok_bg: str
    warn: str
    warn_bg: str
    unk_bg: str
    danger: str
    # 辅助色：从主色延伸出去的两种调子。
    # 只在少数地方用（进度条末端、品牌字渐变、选中态暗部），
    # 用多了就会盖过主色，反而没有重点。
    teal: str = "#7FCFC9"
    violet: str = "#8E7BC9"

    # 直接压在整窗壁纸上的文字色（标题栏、栏目标题、底部状态）。
    # 卡片内部的文字仍用 text/muted——卡片是浅底的，两套不能混用。
    #
    # 这两个值要同时喂给 QSS 和 QColor()，所以用 #AARRGGBB 而不是 rgba()：
    # QColor 认 #AARRGGBB，不认 rgba(...)；QSS 两者都认。
    on_dark: str = "#EDE6F5"
    on_dark_muted: str = "#B9AEB3C4"     # 深底上的次要文字，压暗一档

    # 压暗层：卡片的半透明底色、底栏、日志框。
    # 以前这些是写死的 rgba(24,16,36,…)，那是配昔涟壁纸的深紫黑；
    # 换到 plain（灰蓝）主题上会泛紫。做成 token 后每套主题自己定，
    # 不写就用下面的默认值（中性深灰）。
    veil: str = "rgba(24, 22, 28, 150)"
    veil_hover: str = "rgba(42, 38, 48, 172)"
    veil_footer: str = "rgba(16, 15, 20, 96)"
    veil_log: str = "rgba(12, 11, 16, 210)"

    # 排版
    font_family: str = '"Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", sans-serif'
    radius: int = 11
    radius_lg: int = 18


CYRENE = Theme(
    key="cyrene",
    name="昔涟",
    # 配色依据 A:\Cyrene\prompts\soul.md 第十二节的外貌描述：
    #   「超长柔粉色长发，发尾自然过渡浅青渐变」→ 粉是主色，青是它的延伸
    #   「紫渐变柔和眼眸」「内层星空紫内衬」      → 紫只做点缀，不做主色
    # 三色比例约 粉 7 : 青 2 : 紫 1，跟她的自称比例一个道理——
    # 主调清晰，其余只是让主调更好看。
    #
    # 2026-11-09：默认主题改成深色。
    # 整窗背景换成了 art-reading.png（深色房间看书那张），所以底色、文字、
    # 描边全部翻了一套。卡片仍然是浅色，压在深色壁纸上做「浮起的纸片」。
    #
    # 注意 QSS 的 alpha 陷阱：Qt 样式表里 rgba() 的第四个参数是 0–255，
    # 不是 CSS 的 0–1。写成 rgba(255,255,255,0.92) 会被当成 alpha=0，
    # 卡片直接全透明——上一版就是这么把整屏字弄没的。
    # 所以这里 panel 保持不透明十六进制色，需要半透明的场合单独给 token。
    page="#151020",          # 兜底底色（壁纸没加载时用）
    panel="#FFFFFF",         # 卡片底：不透明，QSS 与 QColor 都能安全解析
    panel_2="#F4ECF2",       # 卡片内的次级层
    border="#E6D2DE",      # 不透明描边（见下方注释，别改成 #AARRGGBB）
    text="#3A2430",          # 卡片内是浅底，文字仍用深色
    muted="#8A7480",
    accent="#DF7BA0",          # 桃粉，主色
    accent_fg="#FFFFFF",
    accent_soft="#F3B4C9",     # 浅粉，渐变尾巴
    ok="#4FAE8C",
    ok_bg="#E4F4EE",
    warn="#DE9070",
    warn_bg="#FBEDE6",
    unk_bg="#F2EDEF",
    danger="#C4567F",
    # 发尾的青，用在进度条末端与悬停描边
    teal="#7FCFC9",
    # 星空紫，只用于标题字渐变与选中态的暗部
    violet="#8E7BC9",
)

# ---------------------------------------------------------------- 三套主题
#
# 三套不是三种风格，是同一个存在的三种时刻：
#
#   cyrene  昔涟    —— 现在的昔涟。粉白为底，日常用它，最贴她本来的样子。
#   mist    浅汐    —— 浅色冷调。用她发尾那抹青做主色，白天光线强时更耐看。
#   indigo  星空夜  —— 深色。soul.md 写「内层星空紫内衬」，紫是她裙摆内侧的颜色，
#                      夜里挂机时用这套，不刺眼。
#
# 三套共享同一套版面、同一个意象（涟漪）、同一组语义色，只换底色与主色深浅。
# 不做成三个无关的皮肤，否则切换主题就像换了个软件。

INDIGO = Theme(
    key="indigo",
    name="星空夜",
    # 底色取星空紫的极深版，不是中性黑——她要的是「夜里的紫」，不是纯黑。
    page="#0E0A14",
    panel="#171222",
    panel_2="#1F1930",
    border="#2C2440",
    text="#EDE6F5",
    muted="#9A8FB0",
    # 主色仍是桃粉，只是压暗一点让它在深底上不刺眼
    accent="#D9739B",
    accent_fg="#0E0A14",
    accent_soft="#E89BB8",
    ok="#5FBF9A",
    ok_bg="#245FBF9A",
    warn="#D68F6B",
    warn_bg="#26D68F6B",
    unk_bg="#269A8FB0",
    danger="#D96A8A",
    # 深色里青和紫可以亮一些，做涟漪与进度条的收尾
    teal="#6FC4BF",
    violet="#A48FD6",
)

MIST = Theme(
    key="mist",
    name="浅汐",
    # 底是极浅的青白，不是灰——雾气的调子来自她发尾，不是中性灰
    page="#F2FAFA",
    panel="#FFFFFF",
    panel_2="#E8F6F6",
    border="#D2EAEA",
    text="#1E3838",
    muted="#6B8A8A",
    # 青做主色，粉退成配角。这是三套里唯一以青为主导的，作为对照
    accent="#3E9E9B",
    accent_fg="#FFFFFF",
    accent_soft="#7CC4C2",
    ok="#3E9E7B",
    ok_bg="#1F3E9E7B",
    warn="#D08A5C",
    warn_bg="#21D08A5C",
    unk_bg="#1F6B8A8A",
    danger="#C45A7A",
    teal="#3E9E9B",
    violet="#9B87C2",
)

PLAIN = Theme(
    key="plain",
    name="简约",
    # 唯一一套不依赖任何美术素材的主题。
    #
    # 为什么要有它：仓库里不带昔涟的图（版权原因），
    # 别人 clone 下来用 cyrene 主题会看到一片加载失败的空白。
    # 这套只用颜色和排版，深浅灰蓝，跟任何壁纸都不冲突，
    # 也让「没有素材」这件事看起来是个正常选择，而不是坏掉。
    #
    # 配色刻意中性：不粉、不青，避免和用户自己换的壁纸打架。
    page="#1C1F26",
    panel="#262A33",
    panel_2="#31363F",
    border="#3D434E",
    text="#E4E7EC",
    muted="#9AA3B0",
    accent="#6E9BE8",
    accent_fg="#FFFFFF",
    accent_soft="#9CBCF0",
    ok="#5BBF8E",
    ok_bg="#265BBF8E",
    warn="#D9A05B",
    warn_bg="#28D9A05B",
    unk_bg="#289AA3B0",
    danger="#E06C7E",
    teal="#5BBFBF",
    violet="#9B8FD6",
    # 深底浅字，直接压在纯色页面上
    on_dark="#E4E7EC",
    on_dark_muted="#B49AA3B0",
    # plain 没有壁纸，卡片可以直接用不透明的面板色，不必做磨砂
    veil="rgba(38, 42, 51, 235)",
    veil_hover="rgba(52, 58, 70, 245)",
    veil_footer="rgba(28, 31, 38, 240)",
    veil_log="rgba(20, 22, 28, 250)",
)

THEMES: dict[str, Theme] = {t.key: t for t in (CYRENE, MIST, INDIGO, PLAIN)}
DEFAULT_THEME = CYRENE.key


def get(key: str) -> Theme:
    """按 key 取主题，未知 key 回落到默认主题。"""
    return THEMES.get(key, CYRENE)


def resolve_for_assets(key: str, has_assets: bool) -> Theme:
    """按「素材是否存在」决定实际用哪套主题。

    为什么需要它：cyrene/mist/indigo 三套都靠昔涟的美术图撑起观感
    （壁纸、星魂、logo）。仓库里不带这些素材（版权原因），
    别人 clone 下来就会看到一堆加载失败的空白——所以要能自动退回 plain。

    规则：
        - 有素材：用用户选的主题
        - 没素材且选的是昔涟系主题：退回 plain
        - 没素材但选的是 plain：就用 plain
    """
    theme = get(key)
    if has_assets:
        return theme
    if theme.key == PLAIN.key:
        return theme
    return PLAIN


def stylesheet(t: Theme) -> str:
    """把主题 token 展开成整窗 QSS。"""
    return f"""
    QWidget {{
        color: {t.text};
        font-family: {t.font_family};
        font-size: 13px;
    }}
    /* Root 是中栏和侧栏共用的容器 objectName。
       这里必须是透明：整窗背景由 WindowBackdrop 画在最底层，
       Root 只要铺一层不透明底色，壁纸就整个被盖住——
       2026-11-09 之前写的是 background-color: 深色底，
       结果「中栏看不到读书图」查了半天，根因就在这一行。 */
    QWidget#Root {{
        background: transparent;
    }}

    /* ---------- 标题栏 ---------- */
    /* 标题栏底色由 TitleBar.paintEvent 自绘（横向渐变 + 星魂1 淡装饰），
       这里不能再设 background-color，否则会把渐变盖掉成纯色。 */
    QWidget#TitleBar {{
        border-bottom: 1px solid rgba(255, 255, 255, 40);
    }}
    QLabel#BrandEn {{
        color: {t.accent};
        font-size: 15px;
        font-weight: 700;
    }}
    /* 品牌字右边那颗小珠子：用星空紫，作为第三种颜色的唯一落点。
       主色粉、辅色青都在数据区用了，紫就退到最安静的地方。 */
    QLabel#BrandDot {{
        color: {t.violet};
        font-size: 15px;
    }}
    QLabel#BrandCn {{
        color: {t.on_dark_muted};
        font-size: 12px;
    }}

    /* ---------- 更新提示条 ---------- */
    /* 之前没写样式，用的是 Qt 默认浅灰底，在深色界面上像贴了张纸。
       outdated 用 property 切换，不要内联 setStyleSheet（会级联到子控件）。 */
    QWidget#UpdateBanner {{
        background-color: rgba(40, 52, 44, 210);
        border-bottom: 1px solid rgba(255, 255, 255, 34);
    }}
    QWidget#UpdateBanner[outdated="true"] {{
        background-color: rgba(92, 52, 40, 220);
    }}
    QLabel#UpdateLabel {{
        color: {t.on_dark};
        font-size: 12px;
    }}
    QWidget#UpdateBanner[outdated="true"] QLabel#UpdateLabel {{
        color: #FFD9C2;
    }}

    /* 自绘的窗口控制按钮容器（最小化/最大化/关闭）。
       按钮本身由 ui/frameless.py 手画，这里只保证容器不挡背景。 */
    QWidget#WindowButtons {{
        background: transparent;
    }}

    /* 设置页的卡片。设置项直接铺在壁纸上会看不清——输入框、
       说明文字都压在她的画上。垫一层足够暗的底把它托起来。 */
    QFrame#SettingsCard {{
        background-color: rgba(18, 12, 26, 218);
        border: 1px solid rgba(255, 255, 255, 40);
        border-radius: 14px;
    }}

    /* ---------- 美图画廊 ---------- */
    QScrollArea#GalleryScroll, QWidget#GalleryInner {{
        background: transparent;
        border: none;
    }}
    /* 图片格子。不加内边距——图要顶到边，圆角靠 border-radius 裁。
       悬停只提亮边框和底色，不做位移：瀑布流里位移会让相邻格跟着抖。 */
    QFrame#GalleryTile {{
        background-color: rgba(255, 255, 255, 18);
        border: 1px solid rgba(255, 255, 255, 30);
        border-radius: 8px;
    }}
    QFrame#GalleryTile:hover {{
        background-color: rgba(223, 123, 160, 40);
        border-color: rgba(223, 123, 160, 180);
    }}
    /* 大图查看器的说明文字 */
    QLabel#ViewerCaption {{
        color: {t.on_dark_muted};
        font-size: 12px;
        letter-spacing: 1px;
    }}
    /* 空状态：图片很淡，文字要压得住 */
    QLabel#EmptyTitle {{
        color: {t.on_dark};
        font-size: 17px;
        font-family: "STXingkai", "华文行楷", {t.font_family};
    }}

    /* ---------- 侧栏状态卡 ---------- */
    QWidget#SideWrap {{
        /* 侧栏背景交给整窗壁纸，不再铺不透明底色，
           否则会挡住 art-reading.png。 */
        background: transparent;
    }}
    QScrollArea#SideScroll, QWidget#SideInner {{
        background: transparent;
        border: none;
    }}
    QLabel#SideHeading {{
        color: {t.on_dark_muted};
        font-size: 11px;
        letter-spacing: 1px;
    }}
    QFrame#GameCard {{
        /* 和队列卡片同一档透明度（150/255），两边观感才统一。 */
        background-color: {t.veil};
        border: 1px solid rgba(255, 255, 255, 44);
        border-radius: {t.radius}px;
    }}
    QFrame#GameCard:hover {{
        background-color: {t.veil_hover};
    }}
    QLabel#GameName {{
        color: {t.on_dark};
        font-size: 13px;
        font-weight: 600;
    }}
    QLabel#GameMeta {{
        color: {t.on_dark_muted};
        font-size: 11px;
    }}
    QLabel#GameStamina {{
        color: {t.on_dark};
        font-size: 12px;
        font-weight: 700;
    }}
    /* 她说的话。用行楷，读起来像旁边有人轻声说了句，而不是一条系统提示。
       这是一个段落（内含一个换行），行距由 line-height 控制，
       不要拆成两个控件——那样两行之间会空出一段，看着像两句话。 */
    QLabel#CyreneQuote {{
        color: {t.on_dark};
        font-size: 15px;
        line-height: 150%;
        font-family: "STXingkai", "华文行楷", {t.font_family};
    }}
    /* 左栏底部那句。位置从标题栏挪过来（2026-11-10）。
       13px 太小：侧栏 286 宽，行楷在这个字号下笔画细得糊成一片，
       折行也碎。提到 15px 并把行距放宽，读起来才像一句话。 */
    QLabel#SideQuote {{
        color: {t.on_dark};
        font-size: 15px;
        line-height: 190%;
        padding: 0 2px 4px 2px;
        font-family: "STXingkai", "华文行楷", {t.font_family};
    }}

    /* ---------- 任务队列 ---------- */
    /* 这两层只是容器，背景要透明才能露出整窗壁纸。
       别用 setStyleSheet("background: transparent")——QSS 会级联到
       TaskRow，把卡片白底也覆盖掉（交接文档坑 #4，这次又踩了一次）。 */
    QScrollArea#QueueScroll, QWidget#QueueInner {{
        background: transparent;
        border: none;
    }}
    /* 队列卡片：半透明，但要保证字能读。
       透明度过低会看不清，过高就把画盖死——平衡点在 150/255 左右：
       还能看见她背后的轮廓和光带，同时「每日委托 3/4」这种小字不糊。 */
    QFrame#TaskRow {{
        background-color: {t.veil};
        border: 1px solid rgba(255, 255, 255, 44);
        border-radius: {t.radius}px;
    }}
    QFrame#TaskRow[active="true"] {{
        background-color: rgba(62, 36, 62, 170);
        border: 1px solid {t.violet};
    }}
    QLabel#TaskName {{
        color: {t.on_dark};
        font-size: 13px;
        font-weight: 600;
    }}
    QLabel#TaskSub {{
        color: {t.on_dark_muted};
        font-size: 11px;
    }}
    QLabel#TaskIndex {{
        color: {t.on_dark_muted};
        background-color: rgba(255, 255, 255, 30);
        border-radius: 6px;
        font-size: 11px;
        font-weight: 700;
    }}
    QLabel#DragHandle {{
        color: rgba(237, 230, 245, 120);
        font-size: 13px;
    }}
    QLabel#TaskIndex[active="true"] {{
        color: {t.accent_fg};
        background-color: {t.accent};
    }}
    QLabel#TaskMode {{
        color: {t.on_dark_muted};
        border: 1px solid rgba(255, 255, 255, 52);
        border-radius: 10px;
        padding: 2px 8px;
        font-size: 10px;
    }}
    QLabel#SectionTitle {{
        /* 栏目标题直接压在整窗壁纸上，用深底版文字色 */
        color: {t.on_dark};
        font-size: 14px;
        font-weight: 700;
    }}
    QLabel#SectionHint {{
        color: {t.on_dark_muted};
        font-size: 11px;
    }}

    /* ---------- 按钮 ---------- */
    /* 通用按钮改成深底浅字，和整窗的深色基调一致。
       底栏的主按钮（Primary）仍是实心桃粉，作为整屏唯一的强落点。 */
    QPushButton {{
        background-color: rgba(255, 255, 255, 30);
        color: {t.on_dark};
        border: 1px solid rgba(255, 255, 255, 44);
        border-radius: 9px;
        padding: 7px 16px;
        font-size: 12px;
    }}
    QPushButton:hover {{
        background-color: rgba(255, 255, 255, 50);
        border-color: {t.accent};
    }}
    QPushButton:disabled {{
        color: rgba(237, 230, 245, 110);
        background-color: rgba(255, 255, 255, 16);
        border-color: rgba(255, 255, 255, 22);
    }}
    QPushButton#Primary {{
        background-color: {t.accent};
        color: {t.accent_fg};
        border: 1px solid {t.accent};
        font-weight: 600;
    }}
    QPushButton#Primary:hover {{
        background-color: {t.accent_soft};
        border-color: {t.accent_soft};
    }}
    QPushButton#Primary:disabled {{
        background-color: rgba(255, 255, 255, 28);
        color: rgba(237, 230, 245, 110);
        border-color: rgba(255, 255, 255, 28);
    }}
    QPushButton#Ghost {{
        background-color: transparent;
        color: {t.on_dark_muted};
        border: 1px solid transparent;
    }}
    QPushButton#Ghost:hover {{
        border-color: rgba(255, 255, 255, 60);
        color: {t.on_dark};
    }}
    QPushButton#RowButton {{
        background-color: transparent;
        color: {t.on_dark_muted};
        border: 1px solid transparent;
        border-radius: 7px;
        padding: 4px 9px;
        font-size: 11px;
    }}
    QPushButton#RowButton:hover {{
        border-color: rgba(255, 255, 255, 60);
        color: {t.on_dark};
    }}
    QPushButton#RowButton:disabled {{
        color: rgba(237, 230, 245, 90);
    }}
    /* 行内的删除按钮：只在鼠标悬停时出现，所以样式要更弱，
       但悬停到它自己身上时用警示色——它一按就把任务从配置里拿掉了。 */
    QPushButton#RowDelete {{
        background-color: transparent;
        color: rgba(237, 230, 245, 110);
        border: none;
        border-radius: 11px;
        font-size: 15px;
        padding: 0;
    }}
    QPushButton#RowDelete:hover {{
        background-color: rgba(224, 108, 126, 170);
        color: #FFFFFF;
    }}

    /* ---------- 底部 ---------- */
    /* 底栏压在壁纸上，用半透明深色而不是实心面板色，
       否则会在窗口最底下留一条割裂的白带。 */
    QWidget#Footer {{
        background-color: {t.veil_footer};
        border-top: 1px solid rgba(255, 255, 255, 36);
    }}
    QLabel#FooterStatus {{
        color: {t.on_dark_muted};
        font-size: 11px;
    }}

    /* ---------- 日志 ---------- */
    QPlainTextEdit#LogView {{
        background-color: {t.veil_log};
        color: {t.on_dark};
        border: 1px solid rgba(255, 255, 255, 40);
        border-radius: {t.radius}px;
        font-family: "Cascadia Mono", "Consolas", monospace;
        font-size: 11px;
        padding: 6px;
        selection-background-color: {t.accent};
        selection-color: {t.accent_fg};
    }}

    /* ---------- 输入类控件 ---------- */
    /* 设置对话框里的输入框、下拉框、数字框、勾选框。
       不写这段的话它们会吃 Windows 默认的浅色外观，
       在深色对话框上白得刺眼，而且字色和底色接近看不清。 */
    QDialog {{
        background-color: {t.page};
    }}
    QLineEdit, QSpinBox, QComboBox {{
        background-color: rgba(255, 255, 255, 28);
        color: {t.on_dark};
        border: 1px solid rgba(255, 255, 255, 52);
        border-radius: 7px;
        padding: 5px 8px;
        font-size: 12px;
        selection-background-color: {t.accent};
        selection-color: {t.accent_fg};
    }}
    QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{
        border-color: {t.accent};
    }}
    QLineEdit:disabled, QSpinBox:disabled, QComboBox:disabled {{
        color: rgba(237, 230, 245, 90);
        background-color: rgba(255, 255, 255, 14);
    }}
    QSpinBox::up-button, QSpinBox::down-button {{
        background-color: rgba(255, 255, 255, 26);
        border: none;
        width: 16px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {t.panel_2};
        color: {t.text};
        border: 1px solid {t.border};
        selection-background-color: {t.accent};
        selection-color: {t.accent_fg};
    }}
    QCheckBox {{
        color: {t.on_dark};
        font-size: 12px;
        spacing: 7px;
    }}
    QCheckBox::indicator {{
        width: 15px;
        height: 15px;
        border: 1px solid rgba(255, 255, 255, 90);
        border-radius: 4px;
        background-color: rgba(255, 255, 255, 20);
    }}
    QCheckBox::indicator:checked {{
        background-color: {t.accent};
        border-color: {t.accent};
    }}
    QLabel {{
        color: {t.on_dark};
    }}

    /* ---------- 滚动条 ---------- */
    QScrollBar:vertical {{
        background: transparent;
        width: 9px;
        margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: {t.border};
        border-radius: 4px;
        min-height: 28px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {t.muted};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        background: transparent;
    }}

    /* ---------- 弹窗 ---------- */
    QMessageBox, QDialog {{
        background-color: {t.page};
    }}
    """


def progress_stylesheet(t: Theme) -> str:
    """进度条容器。

    填充部分改成自绘（见 main_window_new.StaminaBar），因为 QSS 不支持
    CSS 渐变——想做出「粉开头、青收尾」那种发尾过渡，只能用 QPainter 画。
    """
    return f"""
    QFrame#StaminaTrack {{
        background-color: rgba(255, 255, 255, 46);
        border-radius: 2px;
        border: none;
    }}
    """
