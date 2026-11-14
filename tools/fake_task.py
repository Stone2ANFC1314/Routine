# -*- coding: utf-8 -*-
"""假任务：什么都不做，只睡指定秒数然后正常退出。

用来验证队列的并发/后台逻辑，不碰任何游戏或真实工具。
用法：python fake_task.py <秒数> <名字>
"""
import sys
import time

seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 3.0
name = sys.argv[2] if len(sys.argv) > 2 else "fake"

start = time.time()
print(f"[{name}] 开始，将运行 {seconds} 秒", flush=True)
time.sleep(seconds)
print(f"[{name}] 结束，实际 {time.time() - start:.1f} 秒", flush=True)
