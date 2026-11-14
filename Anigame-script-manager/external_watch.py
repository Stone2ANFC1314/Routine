# -*- coding: utf-8 -*-
"""外部任务监控：MaaEnd 和 MAA。

MaaEnd
------
它的任务列表最后一项是「关闭游戏 (PC)」，跑完会把 Endfield.exe 关掉。
所以判断完成的方式很简单：**看游戏进程还在不在**。

    Endfield.exe 消失 → 说明 MaaEnd 跑完了 → 把 MaaEnd 关掉

比盯 /api/logs 猜「是不是没动了」可靠得多。

MAA
---
界面「完成后」勾着「退出 模拟器」+「退出 MAA」，跑完自己会退出。
所以 MAA 不需要外部监控，等进程退出就行。
"""
from __future__ import annotations

import subprocess
import time


def _is_process_running(image_name: str) -> bool:
    """用 tasklist 查进程在不在（比 psutil 稳，不依赖额外包装）。"""
    try:
        r = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {image_name}", "/NH"],
            capture_output=True,
            text=True,
            encoding="gbk",
            errors="replace",
            timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        out = (r.stdout or "").strip()
        if not out:
            return False
        # 没找到时输出是「信息: 没有运行的任务...」这类提示
        if "没有运行" in out or "No tasks" in out or "INFO" in out.upper():
            return False
        return image_name.lower() in out.lower()
    except Exception:
        return False


def wait_maaend_by_game(
    game_process: str = "Endfield.exe",
    max_minutes: int = 60,
    start_timeout: int = 300,
    stop_grace: int = 30,
    poll: float = 5.0,
    log=None,
    should_stop=None,
) -> tuple[bool, str]:
    """等 MaaEnd 跑完：游戏进程消失即视为完成。

    Args:
        game_process: 游戏进程名
        max_minutes: 最长等待；传 0 表示不限时（任务里设成「不限时」时走这条）
        start_timeout: 多久内连游戏进程都没出现，判定没跑起来
        stop_grace: 游戏消失后再等几秒，让 MaaEnd 收尾
        poll: 轮询间隔
    """
    say = log or (lambda _m: None)
    start = time.monotonic()
    # 0 = 不限时。不这么写的话 deadline 会等于 start，循环一次都进不去，
    # 直接报「达到最长等待 0 分钟」——界面上刚把时长清空就会遇到。
    deadline = None if not max_minutes else start + max_minutes * 60

    saw_game = False
    gone_since = None

    while deadline is None or time.monotonic() < deadline:
        if should_stop and should_stop():
            return False, "用户停止"

        running = _is_process_running(game_process)
        elapsed = time.monotonic() - start

        if running:
            if not saw_game:
                saw_game = True
                say(f"    检测到 {game_process}，MaaEnd 正在跑任务")
            gone_since = None
        else:
            if saw_game:
                if gone_since is None:
                    gone_since = time.monotonic()
                    say(f"    {game_process} 已关闭，等 {stop_grace} 秒让 MaaEnd 收尾…")
                elif time.monotonic() - gone_since >= stop_grace:
                    return True, f"{game_process} 已关闭，任务完成"
            else:
                # 还没见过游戏进程
                if elapsed > start_timeout:
                    return False, f"{start_timeout} 秒内没检测到 {game_process}，MaaEnd 可能没跑起来"

        time.sleep(poll)

    # 只有设了上限才会走到这里，所以这句一定是真的超了
    return False, f"达到最长等待 {max_minutes} 分钟"


def wait_task(kind: str, max_minutes: int, log=None, should_stop=None) -> tuple[bool, str]:
    """按 kind 分派。

    目前只有 maaend 需要外部监控；MAA 自己会退出，走进程退出等待。
    """
    if kind == "maaend":
        return wait_maaend_by_game(max_minutes=max_minutes, log=log, should_stop=should_stop)
    return False, f"未知类型 {kind}"


def detect_kind(exe_name: str) -> str | None:
    """从 exe 文件名判断需不需要外部监控。"""
    if exe_name.lower() == "maaend.exe":
        return "maaend"
    return None
