# -*- coding: utf-8 -*-
"""路径解析：让同一份代码在「源码运行」和「PyInstaller 打包成 exe」下都能找到资源。

问题
----
原来代码里到处写 `_REPO = Path(__file__).parent.parent.parent`，
源码跑的时候 `__file__` 指向 `Anigame-script-manager/ui/xxx.py`，
往上数三级正好是项目根。

打包成 exe 之后 `__file__` 变成临时解包目录（`_MEIPASS`）里的路径，
`assets/` 和 `status/` 都不在那儿，于是界面一片空白、状态读不出来。

两种模式的区别
--------------
源码运行：
    项目根/                      ← assets、status 在这里
    ├── assets/
    ├── status/
    └── Anigame-script-manager/  ← 程序在这里

PyInstaller 单文件：
    exe 所在目录/                 ← config.json、logs 应该放这里（可写）
    └── 游戏日常.exe

PyInstaller 运行时解包目录（sys._MEIPASS）：
    ← assets 这类「只读资源」被打包进来，运行时解包到这里

所以：
    resource_dir()  → 找只读资源（assets、status），打包后指向 _MEIPASS
    data_dir()      → 找可写数据（config.json、logs），永远指向 exe/源码旁
"""
from __future__ import annotations

import sys
from pathlib import Path


def is_frozen() -> bool:
    """是不是被 PyInstaller 打包成了 exe。"""
    return getattr(sys, "frozen", False)


def _meipass() -> Path | None:
    """PyInstaller 的运行时解包目录。源码运行时不存在。"""
    base = getattr(sys, "_MEIPASS", None)
    return Path(base) if base else None


def resource_dir() -> Path:
    """只读资源（assets/ 等）的根目录。

    - 打包后：`_MEIPASS`（资源被解包到这里）
    - 源码运行：项目根（本文件在 Anigame-script-manager/ui/ 下，往上三级）
    """
    meipass = _meipass()
    if meipass is not None:
        return meipass
    return Path(__file__).resolve().parent.parent.parent


def data_dir() -> Path:
    """可写数据（config.json、logs/、runtime_stats/）的根目录。

    - 打包后：exe 所在目录 —— 用户能看到、能备份、能改
    - 源码运行：项目根下的 Anigame-script-manager/
    """
    if is_frozen():
        return Path(sys.executable).resolve().parent
    # 本文件在 <项目>/Anigame-script-manager/ui/paths.py
    return Path(__file__).resolve().parent.parent


def code_dir() -> Path:
    """程序代码根目录（Anigame-script-manager/），用于 sys.path 与模块导入。"""
    if is_frozen():
        # 打包后模块都在 exe 里，sys.path 已经由 PyInstaller 处理好
        return data_dir()
    return Path(__file__).resolve().parent.parent


def asset(*parts: str) -> Path:
    """拼一个 assets 下的路径，例如 asset("cyrene", "加工", "logo-trim.png")。"""
    return resource_dir().joinpath("assets", *parts)


def has_cyrene_assets() -> bool:
    """昔涟素材是否齐全。

    仓库里不带这些图（版权），别人 clone 下来就没有。
    界面要据此决定用昔涟主题还是退回「简约」主题，
    否则会看到一整屏加载失败的空白。
    """
    required = [
        ("cyrene", "原图", "art-reading.png"),
        ("cyrene", "加工", "logo-trim.png"),
    ]
    return all(asset(*parts).exists() for parts in required)
