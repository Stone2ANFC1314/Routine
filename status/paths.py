# -*- coding: utf-8 -*-
"""status 包的路径解析。

为什么需要单独一份
------------------
ui/ 下已经有一个 ui/paths.py，但 status/ 是独立包，主程序只是 import 它，
不该反过来依赖 ui。所以这里放一份等价的实现，两边规则保持一致。

要解决的问题
------------
原来 providers.py / skland.py / accounts.py 都写着：

    WORK = Path(__file__).resolve().parent.parent
    STATE_DIR = WORK / ".dsh"

源码运行时 __file__ 是 <项目>/status/providers.py，往上两级正好是项目根，
状态目录就在那儿。

打包成 exe 之后，__file__ 指向 PyInstaller 的临时解包目录
（_internal/status/providers.pyc），往上两级是 _internal/，
里面没有状态目录 —— 于是 exe 找不到凭据，游戏状态一条都读不出来。

正确做法：可写数据（凭据、缓存）永远放在 exe 旁边，由 data_dir() 给出。

关于目录名
----------
原来叫 `.dsh`，那是当初在本工具的开发环境里随手起的，
看着像是这个程序自己的东西，其实是「森空岛 / 米游社的登录凭据」。

2026-11-12 改成 `.ripple`，跟程序名对上。
旧的 `.dsh` 不会被删除，find_state_dir() 在找不到新目录时会退回去读它，
所以已经登录过的凭据不用重新扫码。
"""
from __future__ import annotations

import sys
from pathlib import Path

# 新的状态目录名
STATE_NAME = ".ripple"
# 兼容：以前用过这个名字，里面可能还有有效凭据
LEGACY_NAMES = (".dsh",)


def data_dir() -> Path:
    """可写数据的根目录。

    - 打包后：exe 所在目录（用户能看到、能备份）
    - 源码运行：项目根（status/ 的上一级）
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def state_dir() -> Path:
    """凭据与缓存的存放目录（.ripple/）。"""
    return data_dir() / STATE_NAME


def find_state_dir() -> Path:
    """定位状态目录，按「新名字 → 旧名字」的顺序找。

    1. `<程序目录>/.ripple`
    2. `<程序目录>/.dsh`（旧版遗留，还带着有效登录态）
    3. `<源码目录>/.ripple`
    4. `<源码目录>/.dsh`

    都不存在就返回新路径（调用方会自己创建）。
    """
    data_root = data_dir()

    candidates = [data_root / STATE_NAME]
    candidates += [data_root / n for n in LEGACY_NAMES]

    # 打包后 exe 可能被挪走，而数据还留在源码目录，这里补一次尝试
    src_root = Path(__file__).resolve().parent.parent
    if src_root != data_root:
        candidates.append(src_root / STATE_NAME)
        candidates += [src_root / n for n in LEGACY_NAMES]

    for p in candidates:
        if p.exists():
            return p

    return state_dir()
