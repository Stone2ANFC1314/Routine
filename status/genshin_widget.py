# -*- coding: utf-8 -*-
"""原神体力：走 widget 接口绕过 dailyNote 的 1034 风控。

发现过程
--------
参考 https://github.com/FufuLauncher/FufuLauncher
它的 DailyNoteService 在遇到 1034 时会改用 widget 接口：

    RecordApiBase + "/aapi/widget/v2?game_id=2"

实测结果（2026-10-30）：
    dailyNote  → 1034（风控）
    widget     → retcode 0，能拿到完整数据

关键细节
--------
1. 完整路径：
   https://api-takumi-record.mihoyo.com/game_record/app/genshin/aapi/widget/v2?game_id=2

2. 签名 salt 用 **CnX4**（xV8v4Qu54lUKrEYFZkJhB8cuOh9Asafs），
   不是 FufuLauncher 代码里写的 CnX6。试 X6 会 -10001。

3. query 就写 `game_id=2`，参与签名。

4. 需要带上：
   x-rpc-tool_version: v6.6.1-gr-cn
   x-rpc-page:         v6.6.1-gr-cn_#/ys
   x-rpc-app_version:  2.112.0
"""
from __future__ import annotations

import hashlib
import random
import time
from typing import Any

import aiohttp

WIDGET_URL = (
    "https://api-takumi-record.mihoyo.com"
    "/game_record/app/genshin/aapi/widget/v2?game_id=2"
)

APP_VERSION = "2.112.0"
TOOL_VERSION = "v6.6.1-gr-cn"
PAGE = "v6.6.1-gr-cn_#/ys"

SALT_X4 = "xV8v4Qu54lUKrEYFZkJhB8cuOh9Asafs"

UA = (
    "Mozilla/5.0 (Linux; Android 13; M2101K9C Build/TKQ1.220829.002; wv) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/108.0.5359.128 "
    f"Mobile Safari/537.36 miHoYoBBS/{APP_VERSION}"
)


def _md5(s: str) -> str:
    return hashlib.md5(s.encode()).hexdigest()


def _ds(query: str = "") -> str:
    t = str(int(time.time()))
    r = str(random.randint(100000, 200000))
    return f"{t},{r},{_md5(f'salt={SALT_X4}&t={t}&r={r}&b=&q={query}')}"


def _headers(cookies: dict[str, str]) -> dict[str, str]:
    return {
        "x-rpc-app_version": APP_VERSION,
        "x-rpc-client_type": "5",
        "x-rpc-device_id": cookies.get("_MHYUUID", ""),
        "x-rpc-device_fp": cookies.get("DEVICEFP", ""),
        "x-rpc-device_name": "Xiaomi M2101K9C",
        "x-rpc-device_model": "M2101K9C",
        "x-rpc-sys_version": "13",
        "x-rpc-channel": "xiaomi",
        "x-rpc-app_id": "bll8iq97cem8",
        "x-rpc-lang": "zh-cn",
        "x-rpc-game_biz": "hk4e_cn",
        "x-rpc-tool_version": TOOL_VERSION,
        "x-rpc-page": PAGE,
        "X-Requested-With": "com.mihoyo.hyperion",
        "Accept": "application/json",
        "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "User-Agent": UA,
        "Cookie": "; ".join(f"{k}={v}" for k, v in cookies.items() if v),
        "DS": _ds("game_id=2"),
    }


async def fetch_genshin_widget(
    session: aiohttp.ClientSession, cookies: dict[str, str]
) -> dict[str, Any]:
    """拿原神实时便笺（树脂、委托、派遣）。返回原始 JSON。"""
    async with session.get(
        WIDGET_URL, headers=_headers(cookies), timeout=25
    ) as r:
        return await r.json(content_type=None)


def summarize(data: dict[str, Any]) -> dict[str, Any]:
    """从 widget 返回里提取面板要用的字段。"""
    resin = data.get("current_resin")
    max_resin = data.get("max_resin")
    fin = data.get("finished_task_num", 0)
    total = data.get("total_task_num", 4)
    exp = data.get("current_expedition_num", 0)
    max_exp = data.get("max_expedition_num", 0)

    # 树脂恢复时间（秒）
    recover = data.get("resin_recovery_time")
    try:
        recover_min = int(recover) // 60 if recover else None
    except (TypeError, ValueError):
        recover_min = None

    return {
        "resin": resin,
        "max_resin": max_resin,
        "commission_done": fin,
        "commission_total": total,
        "daily_done": fin >= total,
        "expedition": exp,
        "max_expedition": max_exp,
        "recover_min": recover_min,
    }


if __name__ == "__main__":
    import asyncio
    import json
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from providers import dpapi_decrypt
    from paths import find_state_dir

    async def _main() -> None:
        # 别写死账号文件名：取状态目录里第一个 accounts/*.bin。
        # 以前这里钉的是开发者自己的账号文件名，还指向改名前的旧目录名。
        acc_dir = find_state_dir() / "accounts"
        files = sorted(acc_dir.glob("*.bin")) if acc_dir.exists() else []
        if not files:
            print(f"没找到已登录的账号：{acc_dir}")
            return
        ck = json.loads(dpapi_decrypt(files[0].read_bytes()))
        print(f"用账号 {files[0].stem}")
        async with aiohttp.ClientSession() as s:
            raw = await fetch_genshin_widget(s, ck)
        print(f"retcode = {raw.get('retcode')}")
        if raw.get("retcode") == 0:
            d = raw.get("data") or {}
            print(json.dumps(summarize(d), ensure_ascii=False, indent=2))

    asyncio.run(_main())
