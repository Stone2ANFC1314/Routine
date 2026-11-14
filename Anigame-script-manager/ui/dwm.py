# -*- coding: utf-8 -*-
"""Windows DWM 窗口圆角。

为什么用 DWM 而不是 setMask
---------------------------
setMask(QRegion) 是位图级遮罩，边缘没有抗锯齿，圆角会呈锯齿状。
DWM 的 DWMWA_WINDOW_CORNER_PREFERENCE 是窗口管理器原生的圆角，
抗锯齿由系统完成，效果和普通系统窗口一致。

要求 Windows 11（build 22000+）。Win10 没有这个属性，
调用会静默失败——那种情况下退回「直角」，不再用 setMask 锯齿。
"""
from __future__ import annotations

import ctypes
import sys

# DWM 窗口属性常量（winuser / dwmapi）
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWCP_DEFAULT = 0
DWMWCP_DONOTROUND = 1
DWMWCP_ROUND = 2


def apply_round_corners(hwnd: int, rounded: bool) -> bool:
    """设置窗口的 DWM 圆角偏好。

    Args:
        hwnd: 窗口句柄（int(winId())）
        rounded: True = 圆角，False = 直角

    Returns:
        True 表示调用成功（系统支持并接受了这个属性）。
    """
    try:
        dwmapi = ctypes.windll.dwmapi
    except AttributeError:
        return False

    value = DWMWCP_ROUND if rounded else DWMWCP_DONOTROUND
    # HRESULT；S_OK = 0
    hr = dwmapi.DwmSetWindowAttribute(
        ctypes.c_void_p(hwnd),
        DWMWA_WINDOW_CORNER_PREFERENCE,
        ctypes.byref(ctypes.c_int(value)),
        ctypes.sizeof(ctypes.c_int),
    )
    return hr == 0


def supports_dwm_rounding() -> bool:
    """当前系统是否支持 DWM 圆角（Win11 build 22000+）。"""
    try:
        v = sys.getwindowsversion()
    except AttributeError:
        return False
    return v.build >= 22000
