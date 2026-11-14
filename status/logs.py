# -*- coding: utf-8 -*-
"""从各工具的日志里判断「今天清完没有」。

为什么走日志
------------
米游社 dailyNote 被账号级风控（1034），拿不到体力/委托完成度。
但每个工具自己跑完都会留日志，且信息比接口更细：
BetterGI 写了「当前刷取情况：原粹树脂(4/5)」「今日奖励已领取」，
MAA 写了 `AllTasksCompleted`，绝区零写了「一条龙 … 全部结束」。

这些日志是本地文件，稳定、不依赖网络、也不需要账号。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path


@dataclass
class LogVerdict:
    """一个工具的日志结论。"""

    tool: str
    found_today: bool = False
    finished: bool = False          # 有明确的「跑完了」信号
    last_run: datetime | None = None
    details: list[str] = field(default_factory=list)
    note: str = ""


def _today_logs(pattern: str, root: Path, suffix: str = ".log") -> list[Path]:
    if not root.exists():
        return []
    return sorted(
        (p for p in root.rglob(f"*{suffix}") if p.is_file()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


# ---------------------------------------------------------------- BetterGI
BG_LOG_DIR = Path(r"A:\BetterGI\log")


def parse_bettergi(day: date | None = None) -> LogVerdict:
    """BetterGI 的日志名带日期：better-genshin-impactYYYYMMDD.log"""
    day = day or date.today()
    v = LogVerdict("BetterGI")
    stamp = day.strftime("%Y%m%d")
    f = BG_LOG_DIR / f"better-genshin-impact{stamp}.log"
    if not f.exists():
        v.note = "今天还没跑过"
        return v

    v.found_today = True
    v.last_run = datetime.fromtimestamp(f.stat().st_mtime)
    text = f.read_text(encoding="utf-8", errors="replace")

    # 一条龙结束
    if "一条龙和配置组任务结束" in text:
        v.finished = True
        v.details.append("一条龙流程跑完")

    # 树脂使用情况
    m = re.findall(r"当前刷取情况：\"([^\"]+)\"", text)
    if m:
        v.details.append(f"刷取 {m[-1]}")

    # 本次消耗（接口给不了这个，日志才有）
    used = re.findall(r"使用 \"([^\"]+)\", 数量：(\d+)", text)
    if used:
        total: dict[str, int] = {}
        for name, n in used:
            total[name] = total.get(name, 0) + int(n)
        parts = [f"{k} {n}" for k, n in total.items()]
        v.details.append("消耗 " + "、".join(parts))

    # 每日奖励
    if "今日奖励已领取" in text:
        v.details.append("每日奖励已领")
    # 纪行
    if "纪行：\"一键领取\"" in text or "纪行：\"无需领取\"" in text:
        v.details.append("纪行已处理")
    # 探索派遣
    if "探索派遣：\"完成\"" in text or "探索派遣：\"领取" in text:
        v.details.append("派遣已收")

    return v


# ---------------------------------------------------------------- 绝区零
ZZZ_LOG_DIR = Path(r"A:\ZZZ\ZZZ-auto\.log")


def parse_zzz(day: date | None = None) -> LogVerdict:
    day = day or date.today()
    v = LogVerdict("绝区零")
    if not ZZZ_LOG_DIR.exists():
        v.note = "找不到日志目录"
        return v

    # 当前 log.txt + 按日期归档的 log.txt.YYYY-MM-DD
    candidates = [ZZZ_LOG_DIR / "log.txt"]
    archived = ZZZ_LOG_DIR / f"log.txt.{day.isoformat()}"
    if archived.exists():
        candidates.insert(0, archived)

    for f in candidates:
        if not f.exists():
            continue
        mtime = datetime.fromtimestamp(f.stat().st_mtime)
        text = f.read_text(encoding="utf-8", errors="replace")

        # 只认今天的（归档文件天然是当天；log.txt 要看修改时间）
        if f.name == "log.txt" and mtime.date() != day:
            continue

        v.found_today = True
        v.last_run = mtime
        if "指令[ 一条龙 ] 执行成功 返回状态 全部结束" in text:
            v.finished = True
            v.details.append("一条龙跑完")

        # 各应用状态
        for app in ("领取每日奖励", "每日任务", "丽都周纪", "恶名狩猎", "兑换码"):
            if f"执行应用 {app}" in text:
                v.details.append(f"含 {app}")
        if not v.details:
            v.details.append("有运行记录")
        break

    if not v.found_today:
        v.note = "今天还没跑过"
    return v


# ---------------------------------------------------------------- MaaEnd
MAAEND_DEBUG = Path(r"A:\MaaEnd\debug")


def parse_maaend(day: date | None = None) -> LogVerdict:
    day = day or date.today()
    v = LogVerdict("MaaEnd")
    if not MAAEND_DEBUG.exists():
        v.note = "找不到日志目录"
        return v

    # 文件形如 2026-10-29-1.log
    pat = day.strftime("%Y-%m-%d")
    files = sorted(MAAEND_DEBUG.glob(f"{pat}*.log"), reverse=True)
    if not files:
        v.note = "今天还没跑过"
        return v

    v.found_today = True
    text = ""
    for f in files:
        text += f.read_text(encoding="utf-8", errors="replace")
        v.last_run = datetime.fromtimestamp(f.stat().st_mtime)

    # MaaEnd 真正跑任务时 maafw 会输出 task 链的名字与结果。
    # 只开窗口、切配置的话这里什么都不该命中。
    real_task = re.search(r"\[TaskInput\]|task_id|TaskChain|run_task|开始任务\s*[:：]", text)
    completed = re.search(r"AllTasksCompleted|任务链完成|全部任务完成|run_task.*?completed", text)

    if completed:
        v.finished = True
        v.details.append("任务链完成")
    elif real_task:
        v.details.append("有任务执行记录，未看到完成信号")
    else:
        # 只有打开/关闭软件，没有真正跑任务
        v.finished = False
        v.details.append("只有开关记录，没跑任务")
        v.note = "今天还没真正跑过"

    return v


# ---------------------------------------------------------------- MAA
MAA_DEBUG = Path(r"A:\MAA\debug")


def parse_maa(day: date | None = None) -> LogVerdict:
    day = day or date.today()
    v = LogVerdict("MAA")
    f = MAA_DEBUG / "asst.log"
    if not f.exists():
        v.note = "找不到日志"
        return v

    if datetime.fromtimestamp(f.stat().st_mtime).date() != day:
        v.note = "今天还没跑过"
        return v

    v.found_today = True
    v.last_run = datetime.fromtimestamp(f.stat().st_mtime)
    text = f.read_text(encoding="utf-8", errors="replace")

    if "AllTasksCompleted" in text:
        v.finished = True
        v.details.append("全部任务完成")

    # 最后一条 AllTasksCompleted 的任务链
    chains = re.findall(r'AllTasksCompleted \{.*?"taskchain":"(\w+)"', text)
    if chains:
        v.details.append(f"最后任务链 {chains[-1]}")

    # 各任务链完成情况
    completed = re.findall(r'TaskChainCompleted \{.*?"taskchain":"(\w+)"', text)
    if completed:
        uniq = list(dict.fromkeys(completed))
        v.details.append("完成 " + "/".join(uniq[:8]))

    if not v.details:
        v.details.append("有运行记录")
    return v


# ---------------------------------------------------------------- March7th
M7A_LOG_DIR = Path(r"A:\March7thAssistant_full\logs")


def parse_march7th(day: date | None = None) -> LogVerdict:
    day = day or date.today()
    v = LogVerdict("March7th")
    f = M7A_LOG_DIR / f"{day.isoformat()}.log"
    if not f.exists():
        v.note = "今天还没跑过"
        return v

    v.found_today = True
    v.last_run = datetime.fromtimestamp(f.stat().st_mtime)
    text = f.read_text(encoding="utf-8", errors="replace")

    # March7th 用分隔线标记阶段完成
    if "全部任务完成" in text or "任务完成" in text:
        v.finished = True
        v.details.append("任务完成")

    stages = re.findall(r"当前阶段 (\d+)/(\d+)", text)
    if stages:
        cur, total = stages[-1]
        v.details.append(f"进行到 {cur}/{total}")

    if "开始运行" in text:
        v.details.append("有启动记录")

    if not v.details:
        v.details.append("有运行记录")
    return v


# ---------------------------------------------------------------- 汇总
PARSERS = {
    "genshin": parse_bettergi,
    "zzz": parse_zzz,
    "endfield": parse_maaend,
    "starrail": parse_march7th,
    "arknights": parse_maa,
}


def all_verdicts(day: date | None = None) -> dict[str, LogVerdict]:
    day = day or date.today()
    return {key: fn(day) for key, fn in PARSERS.items()}


if __name__ == "__main__":
    import sys

    out = sys.stdout
    for key, v in all_verdicts().items():
        state = "已跑完" if v.finished else ("跑过但没完成" if v.found_today else "今天没跑")
        when = v.last_run.strftime("%H:%M") if v.last_run else "-"
        print(f"{v.tool:<12} {state:<12} {when}")
        for d in v.details:
            print(f"    {d}")
        if v.note:
            print(f"    · {v.note}")
