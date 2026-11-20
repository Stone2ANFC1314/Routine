# -*- coding: utf-8 -*-
"""默认任务清单。

新装（或第一次启动）时用它填充队列，省得用户对着空界面不知道从哪加。

为什么要把路径写成「猜测的默认位置」而不是留空：
留空的话每一条都会显示「脚本路径为空，已跳过」，看起来像坏了。
这里按各家工具的常见安装位置填上，用户点「设置」改成自己的路径即可。
路径不对时任务行会显示「路径不存在」，也不会真的去启动什么。

2026-11-20 改动
---------------
原来这里直接写死了开发机上的盘符（`A:\\BetterGI\\...`），别人拿来一看
全是红的——他们的工具根本不装在 A 盘。而且把作者自己的目录结构
暴露在了公开仓库里。

现在改成：先按工具名在常见位置里找一遍（各盘根目录、Program Files、
用户目录下的常见文件夹），找到哪个用哪个；一个都找不到才退回
「盘符未知」的形式，用户点「设置」自己选。
"""
from __future__ import annotations

import string
from pathlib import Path
from typing import Any


def _candidate_roots() -> list[Path]:
    """工具可能装在哪。按优先级排，找到就停。"""
    roots: list[Path] = []

    # 1) 各盘根目录。游戏工具大多是绿色版，习惯直接丢在盘根。
    for letter in string.ascii_uppercase:
        drive = Path(f"{letter}:\\")
        try:
            if drive.exists():
                roots.append(drive)
        except OSError:
            continue

    # 2) 常见安装目录
    for base in (
        Path.home() / "Desktop",
        Path.home() / "Documents",
        Path.home() / "Downloads",
        Path.home(),
    ):
        roots.append(base)

    for pf in (Path("C:/Program Files"), Path("C:/Program Files (x86)")):
        if pf.exists():
            roots.append(pf)

    return roots


def _find_tool(*relative: str) -> str:
    """在候选根目录里找一个 exe，返回绝对路径；找不到返回空串。

    `relative` 是可能出现的相对路径片段，按顺序试。例如
    ("BetterGI/BetterGI.exe", "BetterGI.exe") —— 先试带目录的。

    两个层次都试：
      1. 根目录下直接拼（`<根>/<相对路径>`）
      2. 根目录的每个子文件夹里，按文件名找（`<根>/<子目录>/<文件名>`）
      3. 再深一层（常见于 `ZZZ/ZZZ-auto/xxx.exe` 这种多套一层的）

    Windows 上遍历盘根会撞到各种权限错误（System Volume Information、
    回收站、别的用户目录）。这些都必须吞掉继续往下扫，不能因为
    某个目录读不了就把整轮搜索放弃掉 —— 之前就是这样漏掉了 ZZZ。
    """
    names: list[str] = []
    for rel in relative:
        base = Path(rel).name
        if base not in names:
            names.append(base)

    def _probe_dir(folder: Path, depth: int) -> str:
        """在 folder 里找名字匹配的 exe，最多再往下 depth 层。"""
        try:
            entries = list(folder.iterdir())
        except OSError:
            return ""

        # 先看本层有没有
        for entry in entries:
            try:
                if entry.is_file() and entry.name in names:
                    return str(entry)
            except OSError:
                continue

        if depth <= 0:
            return ""

        # 再往下
        for entry in entries:
            try:
                if not entry.is_dir():
                    continue
            except OSError:
                continue
            hit = _probe_dir(entry, depth - 1)
            if hit:
                return hit
        return ""

    for root in _candidate_roots():
        try:
            if not root.is_dir():
                continue
        except OSError:
            continue

        # 1) 根目录下直接拼
        for rel in relative:
            try:
                direct = root / rel
                if direct.is_file():
                    return str(direct)
            except OSError:
                continue

        # 2) 和 3) 递归往下找
        hit = _probe_dir(root, 2)
        if hit:
            return hit

    return ""


# 各工具常见的位置写法。找不到就留空，让用户自己选。
_BETTERGI = _find_tool("BetterGI/BetterGI.exe", "BetterGI.exe")
_MAAEND = _find_tool("MaaEnd/MaaEnd.exe", "MaaEnd.exe")
_ZZZ = _find_tool("ZZZ-auto/OneDragon-Launcher.exe", "OneDragon-Launcher.exe")
_M7A = _find_tool("March7thAssistant/m7a.exe", "m7a.exe")
_MAA = _find_tool("MAA/MAA.exe", "MAA.exe")


def default_tasks() -> list[dict[str, Any]]:
    """返回一份可直接写进 config.json 的任务列表。"""
    return [
        {
            "enabled": True,
            "name": "原神 · BetterGI 一条龙",
            "script_path": _BETTERGI,
            "order": 1,
            "timeout_minutes": 0,
            "timeout_action": "kill_and_continue",
            "use_args": True,
            "args": "startOneDragon",
            "wait_mode": "direct_process",
            "wait_process_name": "",
            "confirm_enter_delay_seconds": 0,
            "concurrent_group": "",
            "concurrent_policy": "wait_all",
            "enable_watchdog": False,
            "process_keywords": [],
            "window_keywords": [],
            "launcher_process": "",
            "main_process": "",
            "game_process": "",
            "run_in_background": False,
        },
        {
            "enabled": True,
            "name": "终末地 · MaaEnd",
            "script_path": _MAAEND,
            "order": 2,
            "timeout_minutes": 90,
            "timeout_action": "kill_and_continue",
            "use_args": False,
            "args": "",
            "wait_mode": "direct_process",
            "wait_process_name": "",
            "confirm_enter_delay_seconds": 0,
            "concurrent_group": "",
            "concurrent_policy": "wait_all",
            "enable_watchdog": False,
            "process_keywords": [],
            "window_keywords": [],
            "launcher_process": "",
            "main_process": "",
            "game_process": "",
            "run_in_background": False,
        },
        {
            "enabled": True,
            "name": "绝区零 · 一条龙",
            "script_path": _ZZZ,
            "order": 3,
            "timeout_minutes": 45,
            "timeout_action": "kill_and_continue",
            "use_args": True,
            "args": "-o -c",
            "wait_mode": "direct_process",
            "wait_process_name": "",
            "confirm_enter_delay_seconds": 0,
            "concurrent_group": "",
            "concurrent_policy": "wait_all",
            "enable_watchdog": False,
            "process_keywords": [],
            "window_keywords": [],
            "launcher_process": "",
            "main_process": "",
            "game_process": "",
            "run_in_background": False,
        },
        {
            "enabled": True,
            "name": "崩坏：星穹铁道 · 三月七小助手",
            "script_path": _M7A,
            "order": 4,
            "timeout_minutes": 90,
            "timeout_action": "kill_and_continue",
            "use_args": True,
            # --after-finish Exit 是「跑完退出游戏」。
            #
            # 官方文档（assets/docs/Tutorial.md）原话：
            #   「其中 `退出` 指退出游戏」
            # 所以 Exit 关的是星铁本体，不是 Launcher 自己 ——
            # 这正是我们要的：M7A 默认跑完把游戏留在那儿，
            # 加上这个参数它就会自己关掉，不用队列事后 taskkill。
            #
            # 不能省略这个参数：不写的话走 M7A 自己配置里的 after_finish，
            # 而那可能是关机/睡眠，会和本程序的「结束后操作」打架。
            "args": "main --after-finish Exit",
            "wait_mode": "direct_process",
            "wait_process_name": "",
            "confirm_enter_delay_seconds": 0,
            "concurrent_group": "",
            "concurrent_policy": "wait_all",
            "enable_watchdog": False,
            "process_keywords": [],
            "window_keywords": [],
            "launcher_process": "",
            "main_process": "",
            "game_process": "",
            "run_in_background": False,
        },
        {
            "enabled": True,
            "name": "明日方舟 · MAA",
            "script_path": _MAA,
            "order": 5,
            "timeout_minutes": 60,
            "timeout_action": "kill_and_continue",
            "use_args": False,
            "args": "",
            # 启动后不等待：MAA 走模拟器 ADB 通道，自己会结束。
            # 而且它要排在最后，否则会和下一个任务抢模拟器。
            "wait_mode": "fire_and_continue",
            "wait_process_name": "",
            "confirm_enter_delay_seconds": 0,
            "concurrent_group": "",
            "concurrent_policy": "wait_all",
            "enable_watchdog": False,
            "process_keywords": [],
            "window_keywords": [],
            "launcher_process": "",
            "main_process": "",
            "game_process": "",
            "run_in_background": False,
        },
    ]
