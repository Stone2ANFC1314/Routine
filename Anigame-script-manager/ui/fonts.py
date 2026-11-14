# -*- coding: utf-8 -*-
"""字体加载：保证界面上的行楷真的生效。

为什么需要显式加载
------------------
Qt 在 venv 里找不到自带的 fonts 目录，会打印
    QFontDatabase: Cannot find font directory ...\\PySide6\\lib\\fonts
这时 QSS 里写的 "STXingkai" 能不能解析到，取决于系统字体能不能被正确枚举。
2026-11-08 就吃过这个亏：QSS 里明明写着行楷，渲染出来是黑体，
截图和真实界面对不上，查了半天以为是字体名写错了。

所以在启动时主动把 STXINGKA.TTF 注册进来，不依赖 Qt 自己找到它。

关于体积
--------
这里**不打包字体文件**。华文行楷是 Windows 随系统分发的（STXINGKA.TTF），
大多数中文 Windows 都有；从系统目录加载，程序体积不增加。
真遇到精简版系统没有这个文件，会退回楷体，再没有才用雅黑——
不会崩，只是不手写。
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase

# 候选：先是行楷（要的那个），再是同类手写感稍弱的兜底。
# 顺序即优先级，取第一个系统里真的装了（或加载成功）的。
BRUSH_FAMILIES = ("STXingkai", "华文行楷", "STKaiti", "华文楷体", "KaiTi")

# 常见字体文件位置。STXINGKA.TTF 就躺在 Windows\Fonts 下。
FONT_SEARCH_PATHS = (
    Path(r"C:\Windows\Fonts\STXINGKA.TTF"),
    Path(r"C:\Windows\Fonts\STXINGKA.ttf"),
    Path(r"C:\Windows\Fonts\STKAITI.TTF"),
)

_loaded = False
_resolved: str | None = None


def ensure_fonts() -> str | None:
    """把行楷注册进 Qt，并返回最终可用的字体族名。

    只做一次，重复调用直接返回上次的结果。
    返回 None 表示一个都没找到，调用方应退回默认字体。
    """
    global _loaded, _resolved
    if _loaded:
        return _resolved
    _loaded = True

    existing = set(QFontDatabase.families())

    # 系统已经能枚举到就不用再注册了
    for family in BRUSH_FAMILIES:
        if family in existing:
            _resolved = family
            return _resolved

    # 枚举不到，主动把文件注册进来
    for path in FONT_SEARCH_PATHS:
        if not path.exists():
            continue
        fid = QFontDatabase.addApplicationFont(str(path))
        if fid < 0:
            continue
        families = QFontDatabase.applicationFontFamilies(fid)
        for family in families:
            if family in BRUSH_FAMILIES or family not in existing:
                _resolved = family
                return _resolved
        if families:
            _resolved = families[0]
            return _resolved

    return None


def brush_font(size: int) -> QFont:
    """拿到行楷 QFont；系统里实在没有就退回雅黑。"""
    family = ensure_fonts()
    if family is None:
        return QFont("Microsoft YaHei UI", size)
    font = QFont(family, size)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    return font


def brush_css_family() -> str:
    """给 QSS 用的 font-family 串，带上兜底。"""
    family = ensure_fonts()
    if family is None:
        return "Microsoft YaHei UI"
    # 把命中的那个排到最前，后面留几个通用兜底
    rest = [f for f in BRUSH_FAMILIES if f != family]
    return ", ".join([f'"{family}"'] + [f'"{f}"' for f in rest[:2]] + ["sans-serif"])
