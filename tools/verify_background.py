# -*- coding: utf-8 -*-
"""验证后台并行逻辑：用假任务跑一遍真实的 ScriptRunnerWorker。

不碰任何游戏或真实工具，只观察时间线：
    - 前台任务应当一个接一个，不重叠
    - 标记为「后台」的任务启动后，队列应当立刻继续
    - 全部前台结束后，应当等待后台收尾

期望的时间线（A=2s 前台, B=3s 后台, C=2s 前台）：
    t=0  A 开始
    t=2  A 结束，B 开始（后台，立刻继续）
    t=2  C 开始          ← 和 B 重叠
    t=4  C 结束
    t=4  等 B 收尾
    t=5  B 结束
"""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "Anigame-script-manager"))

from core import FileLogger, RuntimeStatsManager, ScriptRunnerWorker, TaskConfig  # noqa: E402

PY = sys.executable
FAKE = str(ROOT / "tools" / "fake_task.py")

events: list[tuple[float, str]] = []
lock = threading.Lock()
t0 = time.monotonic()


def mark(msg: str) -> None:
    with lock:
        events.append((time.monotonic() - t0, msg))


def make(name: str, seconds: float, order: int, background: bool) -> TaskConfig:
    t = TaskConfig(
        enabled=True,
        name=name,
        script_path=PY,
        order=order,
        timeout_minutes=2,
        run_in_background=background,
    )
    t.use_args = True
    t.args = f'"{FAKE}" {seconds} {name}'
    return t


tasks = [
    make("A-前台2秒", 2.0, 1, False),
    make("B-后台3秒", 3.0, 2, True),
    make("C-前台2秒", 2.0, 3, False),
]

logger = FileLogger(ROOT / "Anigame-script-manager" / "logs")
stats = RuntimeStatsManager(ROOT / "Anigame-script-manager")
worker = ScriptRunnerWorker(
    tasks=tasks,
    shutdown_after_done=False,
    shutdown_delay_seconds=0,
    logger=logger,
    stats_manager=stats,
)

worker.log_signal.connect(lambda line: mark(line))
worker.finished_signal.connect(lambda had_err: mark(f"=== 队列结束 had_error={had_err} ==="))

print("跑假任务，观察时间线…\n")
worker.run()

print("=== 时间线 ===")
for sec, msg in events:
    print(f"{sec:6.2f}s  {msg}")

# ---- 判定 ----
print("\n=== 判定 ===")
lines = [(s, m) for s, m in events]

def find(pred):
    for s, m in lines:
        if pred(m):
            return s, m
    return None, None

t_bg_start, _ = find(lambda m: "B-后台3秒」已转入后台" in m)
t_c_start, _ = find(lambda m: "开始执行任务：C-前台2秒" in m or ("C-前台2秒" in m and "已启动" in m))
t_wait, _ = find(lambda m: "前台任务已结束，等待" in m)
t_bg_done, _ = find(lambda m: "后台任务「B-后台3秒」已收尾" in m)

ok = True
checks = []

if t_bg_start is None:
    checks.append(("B 转入后台", False, "日志里没找到"))
    ok = False
else:
    checks.append(("B 转入后台", True, f"t={t_bg_start:.2f}s"))

if t_c_start is None:
    checks.append(("C 启动", False, "日志里没找到"))
    ok = False
else:
    checks.append(("C 启动", True, f"t={t_c_start:.2f}s"))

if t_bg_start is not None and t_c_start is not None:
    gap = t_c_start - t_bg_start
    overlapped = gap < 1.5
    checks.append((
        "C 没有等 B 跑完（重叠）",
        overlapped,
        f"B 启动后 {gap:.2f}s C 就启动了" + ("（并行生效）" if overlapped else "（仍是串行！）"),
    ))
    ok = ok and overlapped

if t_wait is None or t_bg_done is None:
    checks.append(("等待后台收尾", False, "日志里没找到"))
    ok = False
else:
    waited = t_bg_done - t_wait
    checks.append((
        "前台结束后确实等了后台",
        t_bg_done >= t_wait,
        f"t={t_wait:.2f}s 开始等，t={t_bg_done:.2f}s 收尾",
    ))

for name, passed, detail in checks:
    # 只用 GBK 能编码的符号：cmd 默认代码页 936，U+2713/U+2717 会抛 UnicodeEncodeError
    print(f"  {'√' if passed else '×'} {name:<26} {detail}")

print()
print("结论：" + ("后台并行生效" if ok else "有问题，没达到预期"))
sys.exit(0 if ok else 1)
