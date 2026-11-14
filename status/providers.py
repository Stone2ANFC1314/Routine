# -*- coding: utf-8 -*-
"""状态数据源：米游社（原神/绝区零/星铁）+ 森空岛（明日方舟）+ MaaEnd（终末地）。

设计原则
--------
1. 每个游戏一个 provider，互不影响：哪个断了只影响它自己那一行。
2. 拿不到实时体力时，退化为「凭据可用 + 角色信息」，不让整块面板崩掉。
3. 凭据只在本地解密，绝不出网。
"""
from __future__ import annotations

import asyncio
import ctypes
import json
import random
import time
import uuid
from ctypes import wintypes
from dataclasses import dataclass, field
from hashlib import md5
from pathlib import Path
from typing import Any

import aiohttp

from status.paths import find_state_dir, data_dir as _data_dir

# 可写数据的根目录。
# 以前是 Path(__file__).parent.parent —— 源码跑没事，打包后 __file__ 指向
# 临时解包目录，.dsh/ 找不到，exe 就一条游戏状态都读不出来。
WORK = _data_dir()
STATE_DIR = find_state_dir()
COOKIE_FILE = STATE_DIR / "mihoyo_cookies.bin"
DEVICE_FILE = STATE_DIR / "device_id.txt"

SALT_APP = "xV8v4Qu54lUKrEYFZkJhB8cuOh9Asafs"
SALT_BBS = "idMMaGYmVgPzh3wxmWudUXKUPGidO7GM"   # BBS 新版 salt（md5(salt&t&r)）

BBS_VERSION = "2.106.2"
UA_APP = (
    "Mozilla/5.0 (Linux; Android 13; M2101K9C Build/TKQ1.220829.002; wv) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/108.0.5359.128 "
    f"Mobile Safari/537.36 miHoYoBBS/{BBS_VERSION}"
)

GAME_NAMES = {1: "崩坏3", 2: "原神", 6: "崩坏：星穹铁道", 8: "绝区零"}
GAME_BIZ = {1: "bh3_cn", 2: "hk4e_cn", 6: "hkrpg_cn", 8: "nap_cn"}


# ---------------------------------------------------------------- DPAPI
class _B(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _blob(data: bytes) -> _B:
    buf = ctypes.create_string_buffer(data, len(data))
    return _B(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))


def dpapi_decrypt(raw: bytes) -> str:
    bi, bo = _blob(raw), _B()
    if not ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(bi), None, None, None, None, 0, ctypes.byref(bo)
    ):
        raise OSError("CryptUnprotectData 失败")
    try:
        return ctypes.string_at(bo.pbData, bo.cbData).decode("utf-8")
    finally:
        ctypes.windll.kernel32.LocalFree(bo.pbData)


def dpapi_encrypt(text: str) -> bytes:
    bi, bo = _blob(text.encode("utf-8")), _B()
    if not ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(bi), None, None, None, None, 0, ctypes.byref(bo)
    ):
        raise OSError("CryptProtectData 失败")
    try:
        return ctypes.string_at(bo.pbData, bo.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(bo.pbData)


def load_mihoyo_cookies() -> dict[str, str] | None:
    if not COOKIE_FILE.exists():
        return None
    try:
        return json.loads(dpapi_decrypt(COOKIE_FILE.read_bytes()))
    except Exception:
        return None


def _device_id(cookies: dict[str, str] | None = None) -> str:
    """优先用 cookie 里的 _MHYUUID（真实设备），否则读本地存的。"""
    if cookies:
        real = cookies.get("_MHYUUID")
        if real:
            return real
    if DEVICE_FILE.exists():
        v = DEVICE_FILE.read_text().strip()
        if v:
            return v.upper()
    v = str(uuid.uuid4()).upper()
    DEVICE_FILE.write_text(v)
    return v


def _ds(params: dict[str, Any]) -> str:
    """BBS 签名：md5(salt&t&r)，r 是 6 位小写字母+数字，不拼 query。"""
    t = str(int(time.time()))
    r = "".join(random.choice("abcdefghijklmnopqrstuvwxyz0123456789") for _ in range(6))
    h = md5(f"salt={SALT_BBS}&t={t}&r={r}".encode()).hexdigest()
    return f"{t},{r},{h}"


# ---------------------------------------------------------------- 数据模型
@dataclass
class GameStatus:
    key: str
    name: str
    ok: bool = False
    # 今日是否已清：True 已清 / False 未清 / None 未知
    daily_done: bool | None = None
    # 体力：当前值 / 上限 / 名称（树脂、电量、开拓力、理智…）
    stamina: int | None = None
    stamina_max: int | None = None
    stamina_label: str = ""
    # 明细行（"每日委托 4/4" 这种）
    details: list[str] = field(default_factory=list)
    note: str = ""
    uid: str = ""
    error: str = ""


# ---------------------------------------------------------------- 米游社
async def _mihoyo_get(
    session: aiohttp.ClientSession,
    url: str,
    params: dict[str, Any],
    cookies: dict[str, str],
    referer: str = "https://webstatic.mihoyo.com",
    game_biz: str = "hk4e_cn",
) -> dict[str, Any]:
    headers = {
        "x-rpc-app_version": BBS_VERSION,
        "x-rpc-client_type": "5",
        "x-rpc-device_id": _device_id(cookies),
        "x-rpc-device_fp": cookies.get("DEVICEFP", ""),
        "x-rpc-device_name": "Xiaomi M2101K9C",
        "x-rpc-device_model": "M2101K9C",
        "x-rpc-sys_version": "13",
        "x-rpc-channel": "xiaomi",
        "x-rpc-app_id": "bll8iq97cem8",
        "x-rpc-game_biz": game_biz,
        "X-Requested-With": "com.mihoyo.hyperion",
        "Origin": referer,
        "Referer": referer,
        "Accept": "application/json, text/plain, */*",
        "User-Agent": UA_APP,
        "DS": _ds(params),
    }
    async with session.get(url, params=params, headers=headers, cookies=cookies, timeout=20) as r:
        return await r.json(content_type=None)


async def fetch_roles(
    session: aiohttp.ClientSession, cookies: dict[str, str]
) -> list[dict[str, Any]]:
    """账号下所有绑定角色。这个接口目前没被风控，可反复调用。"""
    uid = cookies.get("account_id_v2") or cookies.get("ltuid_v2") or ""
    url = "https://api-takumi-record.mihoyo.com/game_record/card/wapi/getGameRecordCard"
    data = await _mihoyo_get(session, url, {"uid": uid}, cookies)
    if data.get("retcode") != 0:
        return []
    return data.get("data", {}).get("list", [])


async def fetch_genshin_ledger(
    session: aiohttp.ClientSession, cookies: dict[str, str], uid: str, server: str
) -> dict[str, Any]:
    """原石流水（hk4e-api，不触发风控）。

    dailyNote 被 1034 挡住，但这条线是通的，能拿到：
      今日/昨日原石、摩拉、本月合计、收入构成
    """
    url = "https://hk4e-api.mihoyo.com/event/ys_ledger/monthInfo"
    params = {"month": 0, "bind_uid": uid, "bind_region": server}
    return await _mihoyo_get(session, url, params, cookies, referer="https://webstatic.mihoyo.com")


async def fetch_genshin_note(
    session: aiohttp.ClientSession, cookies: dict[str, str], uid: str, server: str
) -> dict[str, Any]:
    """原神体力。

    先试 dailyNote（老接口），被 1034 挡住就换 widget 接口。
    widget 是 FufuLauncher 用的兜底路径，实测不被风控。
    """
    url = "https://api-takumi-record.mihoyo.com/game_record/app/genshin/api/dailyNote"
    note = await _mihoyo_get(
        session, url, {"server": server, "role_id": uid}, cookies, game_biz="hk4e_cn"
    )
    if note.get("retcode") == 0:
        return note

    # 兜底：widget 接口
    try:
        from status.genshin_widget import fetch_genshin_widget, summarize

        raw = await fetch_genshin_widget(session, cookies)
        if raw.get("retcode") == 0:
            s = summarize(raw.get("data") or {})
            # 转成和 dailyNote 一样的形状，方便上层统一处理
            return {
                "retcode": 0,
                "data": {
                    "current_resin": s["resin"],
                    "max_resin": s["max_resin"],
                    "finished_task_num": s["commission_done"],
                    "total_task_num": s["commission_total"],
                    "current_expedition_num": s["expedition"],
                    "max_expedition_num": s["max_expedition"],
                },
                "_source": "widget",
            }
    except Exception:
        pass

    return note


async def fetch_zzz_note(
    session: aiohttp.ClientSession, cookies: dict[str, str], uid: str, server: str
) -> dict[str, Any]:
    url = "https://api-takumi-record.mihoyo.com/event/game_record_zzz/api/zzz/note"
    return await _mihoyo_get(
        session, url, {"server": server, "role_id": uid}, cookies,
        referer="https://act.mihoyo.com", game_biz="nap_cn",
    )


async def fetch_starrail_note(
    session: aiohttp.ClientSession, cookies: dict[str, str], uid: str, server: str
) -> dict[str, Any]:
    """星铁开拓力。

    现状（2026-10-30）：整个 hkrpg 命名空间被风控（retcode 10035 = 要过验证码），
    而原神有 widget 备用接口、星铁没有。所以这里目前拿不到数据。

    代码保持可用：哪天米游社放开，不用改就能出数。
    """
    url = "https://api-takumi-record.mihoyo.com/game_record/app/hkrpg/api/note"
    return await _mihoyo_get(
        session, url, {"server": server, "role_id": uid}, cookies, game_biz="hkrpg_cn"
    )


GEETEST_CODES = {10041, 1034, 10035, 5003}


def _geetest_hint(code: int) -> str:
    if code in GEETEST_CODES:
        return "米游社要求人机验证，暂时读不到实时数据"
    if code == -10001:
        return "接口参数校验失败（不是风控）"
    return f"接口返回 {code}"


async def _collect_one_account(
    session: aiohttp.ClientSession,
    account_uid: str,
    cookies: dict[str, str],
    out: dict[str, GameStatus],
) -> None:
    """把一个米游社账号下的角色合进 out。已有角色的话追加序号。"""
    try:
        roles = await fetch_roles(session, cookies)
    except Exception as exc:
        for st in out.values():
            if not st.error:
                st.error = f"读取角色列表失败：{type(exc).__name__}"
        return

    suffix = "" if all(not s.uid for s in out.values()) else f" @{account_uid[-4:]}"

    for game_id, key, fetcher, stamina_name in (
        (2, "genshin", fetch_genshin_note, "树脂"),
        (8, "zzz", fetch_zzz_note, "电量"),
        (6, "starrail", fetch_starrail_note, "开拓力"),
    ):
        r = next((x for x in roles if x.get("game_id") == game_id), None)
        if not r:
            continue

        st = out[key]
        # 已经有角色了（多账号）→ 复制一份
        if st.ok:
            clone = GameStatus(f"{key}_{account_uid}", st.name + suffix, stamina_label=stamina_name)
            clone.uid = str(r.get("game_role_id", ""))
            clone.ok = True
            for item in r.get("data", []):
                clone.details.append(f"{item.get('name')} {item.get('value')}")
            out[clone.key] = clone
            st = clone
        else:
            st.uid = str(r.get("game_role_id", ""))
            st.ok = True
            for item in r.get("data", []):
                st.details.append(f"{item.get('name')} {item.get('value')}")

        try:
            # 绝区零的 note 会偶发 10035（风控抖动），重试几次基本能过
            note = await fetcher(session, cookies, st.uid, r.get("region", "prod_gf_cn"))
            for _ in range(2):
                if key == "zzz" and note.get("retcode") in GEETEST_CODES:
                    await asyncio.sleep(2.5)
                    note = await fetcher(session, cookies, st.uid, r.get("region", "prod_gf_cn"))
                else:
                    break
            code = note.get("retcode")
            if code == 0:
                d = note.get("data") or {}
                if key == "genshin":
                    st.stamina = d.get("current_resin")
                    st.stamina_max = d.get("max_resin")
                    fin, total = d.get("finished_task_num", 0), d.get("total_task_num", 4)
                    st.details.append(f"每日委托 {fin}/{total}")
                    # 「已清」= 委托做完 且 树脂用掉。只做委托不刷本不算清。
                    st.daily_done = fin >= total and _stamina_spent(st)
                elif key == "zzz":
                    # 绝区零的结构是 energy.progress.{current,max}
                    eng_obj = d.get("energy") or {}
                    if isinstance(eng_obj, dict) and "progress" in eng_obj:
                        prog = eng_obj.get("progress") or {}
                        st.stamina = prog.get("current")
                        st.stamina_max = prog.get("max")
                    else:
                        st.stamina = d.get("energy") if isinstance(d.get("energy"), int) else None
                        st.stamina_max = d.get("max_energy")
                    # 活跃度
                    vit = d.get("vitality") or {}
                    if isinstance(vit, dict) and vit.get("max"):
                        st.details.append(f"活跃度 {vit.get('current', 0)}/{vit.get('max')}")
                    # 录像店
                    vs = d.get("vhs_sale") or {}
                    if isinstance(vs, dict) and vs.get("sale_state"):
                        state = vs["sale_state"]
                        st.details.append(
                            "录像店 已营业" if "Done" in str(state) else f"录像店 {state}"
                        )
                    # 悬赏委托
                    bc = d.get("bounty_commission") or {}
                    if isinstance(bc, dict) and bc.get("total"):
                        st.details.append(f"悬赏 {bc.get('num', 0)}/{bc.get('total')}")
                    # 周常
                    wt = d.get("weekly_task") or {}
                    if isinstance(wt, dict) and wt.get("max_point"):
                        st.details.append(f"周常 {wt.get('cur_point', 0)}/{wt.get('max_point')}")
                else:
                    st.stamina = d.get("current_stamina")
                    st.stamina_max = d.get("max_stamina")
                    tr, tr_max = d.get("current_train_score", 0), d.get("max_train_score", 500)
                    st.details.append(f"每日实训 {tr}/{tr_max}")
                    st.daily_done = tr >= tr_max
            else:
                # 原神：dailyNote 被风控，退回到原石流水（hk4e-api 不挡）
                if key == "genshin":
                    try:
                        led = await fetch_genshin_ledger(
                            session, cookies, st.uid, r.get("region", "cn_gf01")
                        )
                        if led.get("retcode") == 0:
                            ld = led.get("data") or {}
                            day = ld.get("day_data") or {}
                            month = ld.get("month_data") or {}
                            st.details.append(
                                f"昨日原石 {day.get('last_primogems', 0)}"
                                f" / 摩拉 {day.get('last_mora', 0)}"
                            )
                            st.details.append(
                                f"本月原石 {month.get('current_primogems', 0)}"
                            )
                            st.note = "体力被米游社风控拦住，这里显示的是原石流水"
                            continue
                    except Exception:
                        pass
                st.note = _geetest_hint(code)
        except Exception as exc:
            st.note = f"读体力失败：{type(exc).__name__}"


_SKLAND_BINDING_CACHE: dict[str, Any] = {}


async def _skland_binding_shared() -> list[dict[str, Any]]:
    """方舟和终末地共用一次 binding 请求。

    森空岛对 binding 限流很严，两个游戏各调一次很容易触发 401。
    """
    if "list" in _SKLAND_BINDING_CACHE:
        return _SKLAND_BINDING_CACHE["list"]

    from status.skland import ensure_cred, get_binding

    creds = await ensure_cred()
    if not creds:
        return []
    cred, token = creds
    async with aiohttp.ClientSession() as session:
        games = await get_binding(session, cred, token)
    _SKLAND_BINDING_CACHE["list"] = games
    _SKLAND_BINDING_CACHE["creds"] = creds
    return games


async def collect_mihoyo() -> dict[str, GameStatus]:
    """原神 / 绝区零 / 星铁。

    用户有两个米游社账号：
      YOUR_MIHOYO_UID —— 原神(GENSHIN_UID) + 绝区零(ZZZ_UID) + 星铁(STARRAIL_UID 六十级老角色)
      YOUR_MIHOYO_UID_2 —— 原神(GENSHIN_UID_2 小号) + 星铁(STARRAIL_UID_2 七十级，平时在玩的)

    所以每个游戏指定从哪个账号读，不把所有角色都列出来。
    """
    from status.accounts import load_all_accounts

    # 游戏 → 该从哪个账号读（None = 任意账号里第一个）
    PREFER = {
        "genshin": "YOUR_MIHOYO_UID",
        "zzz": "YOUR_MIHOYO_UID",
        "starrail": "YOUR_MIHOYO_UID_2",
    }
    # 星铁要精确到这个等级 70 的角色，主号上那个 lv61 的老角色不要
    TARGET_UID = {
        "starrail": "STARRAIL_UID_2",
    }

    out: dict[str, GameStatus] = {
        "genshin": GameStatus("genshin", "原神", stamina_label="树脂"),
        "zzz": GameStatus("zzz", "绝区零", stamina_label="电量"),
        "starrail": GameStatus("starrail", "崩坏：星穹铁道", stamina_label="开拓力"),
    }

    accounts = load_all_accounts()
    if not accounts:
        for st in out.values():
            st.error = "尚未登录米游社"
        return out

    async with aiohttp.ClientSession() as session:
        # 先把每个账号的角色列表拿到
        role_map: dict[str, list[dict]] = {}
        for acc_uid, cookies in accounts.items():
            try:
                role_map[acc_uid] = await fetch_roles(session, cookies)
            except Exception:
                role_map[acc_uid] = []
            await asyncio.sleep(1.2)

        for key in ("genshin", "zzz", "starrail"):
            st = out[key]

            # 指定账号优先
            order = list(accounts.keys())
            pref = PREFER.get(key)
            if pref and pref in order:
                order.remove(pref)
                order.insert(0, pref)

            chosen = None
            for acc_uid in order:
                roles = role_map.get(acc_uid) or []
                for game_id, k in ((2, "genshin"), (8, "zzz"), (6, "starrail")):
                    if k != key:
                        continue
                    hit = next((r for r in roles if r.get("game_id") == game_id), None)
                    if not hit:
                        continue
                    # 有精确 UID 要求时，必须匹配
                    want = TARGET_UID.get(key)
                    if want and str(hit.get("game_role_id")) != want:
                        continue
                    chosen = (acc_uid, accounts[acc_uid], hit)
                    break
                if chosen:
                    break

            if not chosen:
                st.note = "这个账号下没有该游戏角色"
                continue

            acc_uid, cookies, r = chosen
            st.uid = str(r.get("game_role_id", ""))
            st.ok = True
            for item in r.get("data", []):
                st.details.append(f"{item.get('name')} {item.get('value')}")

            fetcher = {
                "genshin": fetch_genshin_note,
                "zzz": fetch_zzz_note,
                "starrail": fetch_starrail_note,
            }[key]

            try:
                note = await fetcher(
                    session, cookies, st.uid, r.get("region", "prod_gf_cn")
                )
                # 绝区零偶发风控，重试
                for _ in range(2):
                    if key == "zzz" and note.get("retcode") in GEETEST_CODES:
                        await asyncio.sleep(2.5)
                        note = await fetcher(
                            session, cookies, st.uid, r.get("region", "prod_gf_cn")
                        )
                    else:
                        break

                code = note.get("retcode")
                if code == 0:
                    d = note.get("data") or {}
                    if key == "genshin":
                        st.stamina = d.get("current_resin")
                        st.stamina_max = d.get("max_resin")
                        fin, total = d.get("finished_task_num", 0), d.get("total_task_num", 4)
                        st.details.append(f"每日委托 {fin}/{total}")
                        st.daily_done = fin >= total and _stamina_spent(st)
                    elif key == "zzz":
                        eng_obj = d.get("energy") or {}
                        if isinstance(eng_obj, dict) and "progress" in eng_obj:
                            prog = eng_obj.get("progress") or {}
                            st.stamina = prog.get("current")
                            st.stamina_max = prog.get("max")
                        else:
                            st.stamina = d.get("energy") if isinstance(d.get("energy"), int) else None
                            st.stamina_max = d.get("max_energy")
                        vit = d.get("vitality") or {}
                        if isinstance(vit, dict) and vit.get("max"):
                            st.details.append(f"活跃度 {vit.get('current', 0)}/{vit.get('max')}")
                        vs = d.get("vhs_sale") or {}
                        if isinstance(vs, dict) and vs.get("sale_state"):
                            state = vs["sale_state"]
                            st.details.append(
                                "录像店 已营业" if "Done" in str(state) else f"录像店 {state}"
                            )
                        bc = d.get("bounty_commission") or {}
                        if isinstance(bc, dict) and bc.get("total"):
                            st.details.append(f"悬赏 {bc.get('num', 0)}/{bc.get('total')}")
                        wt = d.get("weekly_task") or {}
                        if isinstance(wt, dict) and wt.get("max_point"):
                            st.details.append(f"周常 {wt.get('cur_point', 0)}/{wt.get('max_point')}")
                        # 待办：悬赏清空 且 电量用掉。活跃度是随体力自然涨的，
                        # 用掉电量后它会自己满，所以不作为判据。
                        bounty_done = not (
                            isinstance(bc, dict) and bc.get("total")
                            and (bc.get("num") or 0) < bc.get("total")
                        )
                        st.daily_done = bounty_done and _stamina_spent(st)
                    else:
                        st.stamina = d.get("current_stamina")
                        st.stamina_max = d.get("max_stamina")
                        tr = d.get("current_train_score", 0)
                        tr_max = d.get("max_train_score", 500)
                        st.details.append(f"每日实训 {tr}/{tr_max}")
                        # 待办：实训做满 且 开拓力用掉。只领实训不做别的不算清。
                        st.daily_done = tr >= tr_max and _stamina_spent(st)
                else:
                    if key == "genshin":
                        # 原神降级到原石流水
                        try:
                            led = await fetch_genshin_ledger(
                                session, cookies, st.uid, r.get("region", "cn_gf01")
                            )
                            if led.get("retcode") == 0:
                                ld = led.get("data") or {}
                                day = ld.get("day_data") or {}
                                month = ld.get("month_data") or {}
                                st.details.append(
                                    f"昨日原石 {day.get('last_primogems', 0)}"
                                )
                                st.details.append(
                                    f"本月原石 {month.get('current_primogems', 0)}"
                                )
                                st.note = "体力读不到，显示的是原石流水"
                                continue
                        except Exception:
                            pass
                    st.note = _geetest_hint(code)
            except Exception as exc:
                st.note = f"读体力失败：{type(exc).__name__}"

            await asyncio.sleep(1.5)

    return out


# ---------------------------------------------------------------- 明日方舟
async def collect_arknights() -> GameStatus:
    """走森空岛：理智、每日/每周任务、剿灭合成玉。"""
    st = GameStatus("arknights", "明日方舟", stamina_label="理智")

    cred_file = STATE_DIR / "skland_cred.bin"
    from status.skland import ensure_cred, get_player_info, summarize

    creds = await ensure_cred()
    if not creds:
        st.note = "尚未登录森空岛"
        return st
    cred, token = creds

    async with aiohttp.ClientSession() as session:
        try:
            games = await _skland_binding_shared()
        except Exception as exc:
            st.error = f"森空岛读取失败：{exc}"
            return st
        if not games:
            st.note = "森空岛未登录或无绑定角色"
            return st

        ark: dict[str, Any] | None = None
        for g in games:
            if g.get("appCode") == "arknights":
                ark = g
                break
        if not ark:
            st.note = "森空岛账号未绑定明日方舟"
            return st

        bindings = ark.get("bindingList") or []
        if not bindings:
            st.note = "森空岛账号未绑定明日方舟角色"
            return st
        b = bindings[0]
        uid = str(b.get("uid", ""))
        st.uid = uid
        st.ok = True

        try:
            data = await get_player_info(session, cred, uid, token)
            s = summarize(data)
            st.stamina = s["ap_current"]
            st.stamina_max = s["ap_max"]
            if s["daily_max"]:
                st.details.append(f"每日任务 {s['daily_done']}/{s['daily_max']}")
                # 待办：每日任务做满 且 理智用掉。
                st.daily_done = (
                    (s["daily_done"] or 0) >= s["daily_max"] and _stamina_spent(st)
                )
            if s["weekly_max"]:
                st.details.append(f"每周任务 {s['weekly_done']}/{s['weekly_max']}")
            if s["campaign_max"]:
                st.details.append(f"剿灭合成玉 {s['campaign_done']}/{s['campaign_max']}")
            if s["nick"]:
                st.details.insert(0, f"{s['nick']} · {b.get('channelName', '')}")
        except Exception as exc:
            st.note = f"读方舟数据失败：{exc}"

    return st


async def collect_endfield() -> GameStatus:
    """终末地也走森空岛（appCode = endfield），拿理智与每日任务。"""
    st = GameStatus("endfield", "明日方舟：终末地", stamina_label="理智")

    from status.skland import ensure_cred, get_endfield_card

    creds = await ensure_cred()
    if not creds:
        st.note = "尚未登录森空岛"
        return st
    cred, token = creds

    async with aiohttp.ClientSession() as session:
        try:
            games = await _skland_binding_shared()
        except Exception as exc:
            st.error = f"森空岛读取失败：{exc}"
            return st
        if not games:
            st.note = "森空岛未登录或无绑定角色"
            return st

        ef = next((g for g in games if g.get("appCode") == "endfield"), None)
        if not ef:
            st.note = "森空岛账号未绑定终末地"
            return st

        bindings = ef.get("bindingList") or []
        if not bindings:
            st.note = "森空岛账号未绑定终末地角色"
            return st

        # 终末地的结构是 {defaultRole: {roleId, serverId, nickname, level}}
        b = bindings[0]
        role = b.get("defaultRole") or (b.get("roles") or [{}])[0]
        role_id = str(role.get("roleId") or b.get("uid") or "")
        server_id = str(role.get("serverId") or b.get("serverId") or "")
        if not role_id:
            st.note = "读不到终末地角色 ID"
            return st

        st.uid = role_id
        st.ok = True
        if role.get("nickname"):
            st.details.append(f"{role['nickname']} · 权限{role.get('level', '?')}")

        try:
            card = await get_endfield_card(session, cred, role_id, server_id, token)
            d = card.get("detail") or card
            dungeon = d.get("dungeon") or {}
            # 终末地这两个字段返回的是字符串（'132'/'360'），
            # 统一转成整数，别让下游拿去做除法时崩掉。
            st.stamina = _to_int(dungeon.get("curStamina"))
            st.stamina_max = _to_int(dungeon.get("maxStamina"))

            dm = d.get("dailyMission") or {}
            cur, mx = dm.get("dailyActivation"), dm.get("maxDailyActivation")
            if mx:
                st.details.append(f"每日任务 {cur}/{mx}")
                # 待办：每日任务做满 且 理智用掉。
                st.daily_done = (cur or 0) >= mx and _stamina_spent(st)

            bp = d.get("bpSystem") or {}
            if bp.get("curLevel") is not None:
                st.details.append(f"通行证 {bp.get('curLevel')}/{bp.get('maxLevel')}")
        except Exception as exc:
            st.note = f"读终末地数据失败：{exc}"

    return st


# ---------------------------------------------------------------- 汇总
def _to_int(value: Any) -> int | None:
    """接口字段转整数。转不了返回 None。

    存在的原因：有的接口把数字当字符串给（终末地的 curStamina 就是 '132'），
    下游一旦拿去做除法就会 TypeError。
    """
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


# 体力「用掉了」的门槛。
#
# 各游戏满体力上限不同（原神 200、绝区零 240、开拓力 240、理智 135），
# 用比例判断才通用。留 20% 余量，是因为大多数工具不会把体力刷到刚好归零，
# 而且玩家自己也会给第二天留一点。
STAMINA_SPENT_RATIO = 0.2


def _stamina_spent(st: GameStatus) -> bool:
    """体力是否已经用掉。

    读不到体力时返回 True —— 不因为「不知道」就把人判成没做完。
    """
    if st.stamina is None or not st.stamina_max:
        return True
    return st.stamina <= st.stamina_max * STAMINA_SPENT_RATIO


def _merge_log_verdict(st: GameStatus, v) -> None:
    """把日志结论合进 GameStatus。

    优先级：
      1. 接口拿到了准确的完成度（如原神 每日委托 0/4）→ 以接口为准
      2. 接口拿不到（米游社风控 / 森空岛限流）→ 用日志推断

    日志只能证明「跑过」，证明不了「做完了」；接口能给出真实进度，
    但会被风控挡住。所以两边都要，谁有准确数据听谁的。
    """
    has_api_truth = st.daily_done is not None and st.stamina is not None

    if v.found_today:
        if not has_api_truth:
            st.daily_done = bool(v.finished)
        if v.last_run:
            st.details.insert(0, f"上次运行 {v.last_run.strftime('%H:%M')}")
        if not v.finished and not has_api_truth:
            st.note = "今天跑过，但没看到完成信号"
    else:
        if not has_api_truth:
            st.daily_done = False
            st.note = "今天还没跑"


async def collect_all() -> list[GameStatus]:
    mihoyo_task = asyncio.create_task(collect_mihoyo())
    ak_task = asyncio.create_task(collect_arknights())
    ef_task = asyncio.create_task(collect_endfield())

    mihoyo, ak, ef = await asyncio.gather(mihoyo_task, ak_task, ef_task)

    # 固定顺序在前，多账号多出来的条目跟在同游戏后面
    base_keys = ["genshin", "zzz", "starrail"]
    ordered: list[GameStatus] = []
    for k in ("genshin", "zzz"):
        if k in mihoyo:
            ordered.append(mihoyo[k])
    ordered.append(ef)
    if "starrail" in mihoyo:
        ordered.append(mihoyo["starrail"])
    ordered.append(ak)

    # 多账号产生的额外条目
    for k, v in mihoyo.items():
        if k in base_keys:
            continue
        ordered.append(v)

    # 用本地日志覆盖「今天清没清」
    from status.logs import all_verdicts

    verdicts = all_verdicts()
    for st in ordered:
        # 多账号条目（key 形如 genshin_YOUR_MIHOYO_UID）映射回主 key
        lookup = st.key.split("_")[0]
        v = verdicts.get(lookup)
        if not v:
            continue
        _merge_log_verdict(st, v)
        for d in v.details:
            if d not in st.details:
                st.details.append(d)

    return ordered


if __name__ == "__main__":
    statuses = asyncio.run(collect_all())
    for s in statuses:
        flag = {True: "已清", False: "未清", None: "未知"}[s.daily_done]
        stam = f"{s.stamina}/{s.stamina_max}" if s.stamina is not None else "-"
        print(f"{s.name:<16} {flag:<4} {s.stamina_label or '体力'} {stam:<10} uid={s.uid}")
        for d in s.details:
            print(f"    {d}")
        if s.note:
            print(f"    备注：{s.note}")
        if s.error:
            print(f"    错误：{s.error}")
