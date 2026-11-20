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


def _ancestors(start: Path, levels: int = 4):
    """从 start 往上一层层列出来，不含盘符根。"""
    cur = start
    for _ in range(levels):
        yield cur
        parent = cur.parent
        if parent == cur:
            return
        cur = parent


def _has_real_credentials(path: Path) -> bool:
    """这个状态目录里有没有真东西。

    只看「目录存不存在」是不够的：程序每次启动都会 `mkdir` 一个空的
    `.ripple/accounts/`，于是打包目录里会留下一个空壳。如果把这个空壳
    当成「找到了」，就还是会去读一个没有凭据的目录，表现跟数据丢失一样。
    """
    if not path.is_dir():
        return False
    for name in (
        "mihoyo_cookies.bin",
        "skland_cred.bin",
        "skland_full.json",
        "app_stoken.json",
    ):
        if (path / name).is_file():
            return True
    accounts = path / "accounts"
    if accounts.is_dir() and any(accounts.glob("*.bin")):
        return True
    return False


def find_state_dir() -> Path:
    """定位状态目录（凭据放这里）。

    为什么要往上找
    --------------
    PyInstaller 打包时会 `_rmtree(dist/Ripple)` —— 把整个输出目录删掉重建。
    凭据如果放在 `dist/Ripple/.ripple/`，每次升级都会连账号一起消失，
    就像卸载游戏把 mod 一起删了。

    真实目录结构（源码 + 打包）：
        <项目根>/
            .ripple/                 ← 凭据放这里，打包删不到
            dist/
                Ripple/              ← 打包产物，会被整目录删除
                    Ripple.exe

    所以从 exe 所在目录开始向上找，谁先有「带凭据的」`.ripple` 就用谁。
    这样把 dist/Ripple 整个删掉重打包，上一层的凭据还在，
    程序一启动就能捡回来，不用重新扫码。

    查找顺序
    --------
    1. exe 目录/.ripple（旧布局，兼容已经登录过的）
    2. 往上 1~4 级的 .ripple       ← 主路径
    3. 同上，旧名字 .dsh（更早的版本用的）
    4. 都没有 → 在上层新建，而不是在会被删除的 dist/Ripple 里新建

    源码运行时 <项目根>/.ripple 正好是第 2 条，行为不变。
    """
    data_root = data_dir()

    # 1) 就地找（兼容旧布局：凭据已经放在 exe 旁边的情况）
    for name in (STATE_NAME, *LEGACY_NAMES):
        direct = data_root / name
        if _has_real_credentials(direct):
            return direct

    # 2) 逐级向上找
    for base in _ancestors(data_root.parent):
        for name in (STATE_NAME, *LEGACY_NAMES):
            candidate = base / name
            if _has_real_credentials(candidate):
                return candidate

    # 3) 有目录但都是空壳（比如只有打包目录里的空 accounts/）：
    #    挑最靠上的那个继续用，别再往新建的地方分散
    for base in _ancestors(data_root.parent):
        for name in (STATE_NAME, *LEGACY_NAMES):
            candidate = base / name
            if candidate.is_dir():
                return candidate

    # 4) 谁都没有：在上层新建。选 exe 的上一级（dist/ 的兄弟，即项目根），
    #    这样下次打包删掉 dist/Ripple 也不会碰到它。
    for base in _ancestors(data_root.parent):
        if base.parent == base:
            break          # 到盘符根了，别在那儿建
        try:
            base.mkdir(parents=True, exist_ok=True)
            return base / STATE_NAME
        except OSError:
            continue

    return state_dir()
