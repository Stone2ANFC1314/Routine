# -*- coding: utf-8 -*-
"""默认任务清单。

新装（或第一次启动）时用它填充队列，省得用户对着空界面不知道从哪加。

为什么要把路径写成「猜测的默认位置」而不是留空：
留空的话每一条都会显示「脚本路径为空，已跳过」，看起来像坏了。
这里按各家工具的常见安装位置填上，用户点「设置」改成自己的路径即可。
路径不对时任务行会显示「路径不存在」，也不会真的去启动什么。
"""
from __future__ import annotations

from typing import Any


def default_tasks() -> list[dict[str, Any]]:
    """返回一份可直接写进 config.json 的任务列表。"""
    return [
        {
            "enabled": True,
            "name": "原神 · BetterGI 一条龙",
            "script_path": r"A:\BetterGI\BetterGI.exe",
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
            "script_path": r"A:\MaaEnd\MaaEnd.exe",
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
            "script_path": r"A:\ZZZ\ZZZ-auto\OneDragon-Launcher.exe",
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
            "script_path": r"A:\March7thAssistant\m7a.exe",
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
            "script_path": r"A:\MAA\MAA.exe",
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
