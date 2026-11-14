# -*- coding: utf-8 -*-
"""森空岛（明日方舟）登录与状态查询。

登录链路（依据 ProbiusOfficial/Skland_API）：
    手机号+验证码
      → 鹰角通行证 token
      → OAuth2 code (appCode=4ca99fa6b56cc2ba)
      → 森空岛 cred
      → player/info 拿理智与任务进度
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import random
import string
import time
from pathlib import Path
from typing import Any

import aiohttp

from status.paths import data_dir as _data_dir, find_state_dir

# 可写数据在 exe 旁边（打包后），不是临时解包目录。
# 原来写的是 Path(__file__).parent.parent，打包后 .dsh/ 找不到。
WORK = _data_dir()
_STATE = find_state_dir()
CRED_FILE = _STATE / "skland_cred.bin"
# 完整凭据（cred + token），skland_login2.py 写这个
FULL_FILE = _STATE / "skland_full.json"

APP_CODE = "4ca99fa6b56cc2ba"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

HYPERGRYPH = "https://as.hypergryph.com"
ZONAI = "https://zonai.skland.com"

# 森空岛签名算法：
#   sign = MD5( HEX( HMAC-SHA256( path + query + timestamp + headerJson, token ) ) )
#
# ⚠ 关键：HMAC 的密钥是 generate_cred_by_code 返回的 **token**，不是 cred！
#   cred  → 放请求头 cred 字段
#   token → 签名密钥
# 之前拿 cred 当密钥，binding 一直 401「请求异常」，而 user/check 恰好不校验这个，
# 所以看起来像是"凭据有效但接口有问题"。


def load_credentials() -> tuple[str, str] | None:
    """读 (cred, token)。优先完整凭据文件，退回旧格式（只有 cred）。

    旧格式只有 cred，签名会失败，但能让调用方给出明确提示。
    """
    if FULL_FILE.exists():
        try:
            obj = json.loads(FULL_FILE.read_text(encoding="utf-8"))
            cred = str(obj.get("cred", "")).strip()
            token = str(obj.get("token", "")).strip()
            if cred:
                return cred, token or cred
        except Exception:
            pass
    if CRED_FILE.exists():
        try:
            cred = dpapi_decrypt_here(CRED_FILE.read_bytes()).strip()
            if cred:
                return cred, cred
        except Exception:
            pass
    return None


def dpapi_decrypt_here(raw: bytes) -> str:
    """本地 DPAPI 解密（避免和 providers 循环导入）。"""
    import ctypes
    from ctypes import wintypes

    class _B(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    def blob(d: bytes) -> _B:
        buf = ctypes.create_string_buffer(d, len(d))
        return _B(len(d), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))

    bi, bo = blob(raw), _B()
    if not ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(bi), None, None, None, None, 0, ctypes.byref(bo)
    ):
        raise OSError("CryptUnprotectData 失败")
    try:
        return ctypes.string_at(bo.pbData, bo.cbData).decode("utf-8")
    finally:
        ctypes.windll.kernel32.LocalFree(bo.pbData)


def _make_sign(
    cred: str, path: str, body_or_query: str = "", did: str = "", token: str = ""
) -> tuple[dict[str, str], dict[str, str]]:
    """算出签名头。

    参考 endfield-py 1.2.1 的 generate_sign（这是真正跑通的实现）：
      - dId 用**空字符串**，不要自己编 UUID
      - UA 用 App 的 Skland/1.0.0，不是浏览器 UA
      - 请求头里不带 dId / X-Requested-With / Origin / Referer
      - timestamp 用当前时间，不减 2 秒

    签名密钥用 token（不是 cred）。
    """
    if not token:
        token = cred

    timestamp = str(int(time.time()))
    sign_header = {
        "platform": PLATFORM,
        "timestamp": timestamp,
        "dId": "",
        "vName": VNAME,
    }
    sign_header_str = json.dumps(sign_header, separators=(",", ":"))
    raw = f"{path}{body_or_query}{timestamp}{sign_header_str}"
    h = hmac.new(token.encode(), raw.encode(), hashlib.sha256).hexdigest()
    sign = hashlib.md5(h.encode()).hexdigest()

    headers = {
        **_random_headers(),
        "cred": cred,
        "platform": PLATFORM,
        "vName": VNAME,
        "timestamp": timestamp,
        "sign": sign,
        "Content-Type": "application/json",
    }
    return headers, sign_header


# 森空岛 App 的 UA（endfield-py 里用的）
_USER_AGENTS = [
    "Skland/1.0.0 (com.skland.grass; Android; SDK_INT 33; Build/TQ3A.230901.001)",
    "Skland/1.0.0 (com.skland.grass; Android; SDK_INT 34; Build/UP1A.231005.004)",
    "Skland/1.0.0 (com.skland.grass; Android; SDK_INT 35; Build/AP2A.240405.002)",
]

PLATFORM = "3"
VNAME = "1.0.0"


def _random_headers() -> dict[str, str]:
    import random as _r

    return {
        "User-Agent": _r.choice(_USER_AGENTS),
        "Accept-Encoding": "gzip",
        "Connection": "keep-alive",
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }


def _device_id() -> str:
    """森空岛的 dId，存一份保持稳定。

    每次请求都变的话会被当成异常设备，binding 直接 401。
    """
    f = _STATE / ".skland_did"
    if f.exists():
        v = f.read_text(encoding="utf-8").strip()
        if v:
            return v
    import uuid

    v = "B" + uuid.uuid4().hex[:32].upper()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(v, encoding="utf-8")
    return v


def _headers(cred: str) -> dict[str, str]:
    """兼容旧调用：无 body、无 query 的简单签名。"""
    h, _ = _make_sign(cred, "/")
    return h


async def send_phone_code(session: aiohttp.ClientSession, phone: str) -> dict[str, Any]:
    async with session.post(
        f"{HYPERGRYPH}/general/v1/send_phone_code",
        json={"phone": phone, "type": 2},
        headers={"User-Agent": UA, "Content-Type": "application/json"},
        timeout=20,
    ) as r:
        return await r.json(content_type=None)


async def token_by_phone_code(session: aiohttp.ClientSession, phone: str, code: str) -> str:
    async with session.post(
        f"{HYPERGRYPH}/user/auth/v2/token_by_phone_code",
        json={"phone": phone, "code": code},
        headers={"User-Agent": UA, "Content-Type": "application/json"},
        timeout=20,
    ) as r:
        j = await r.json(content_type=None)
        if j.get("status") != 0:
            raise RuntimeError(f"获取通行证 token 失败：{j.get('msg')}")
        return j["data"]["token"]


async def get_cred(session: aiohttp.ClientSession, hyp_token: str) -> tuple[str, str]:
    """用通行证 token 换 (cred, token)。"""
    async with session.post(
        f"{HYPERGRYPH}/user/oauth2/v2/grant",
        json={"token": hyp_token, "appCode": APP_CODE, "type": 0},
        headers={"User-Agent": UA, "Content-Type": "application/json"},
        timeout=20,
    ) as r:
        j = await r.json(content_type=None)
        if j.get("status") != 0:
            raise RuntimeError(f"OAuth2 授权失败：{j.get('msg')}")
        oauth_code = j["data"]["code"]

    async with session.post(
        f"{ZONAI}/api/v1/user/auth/generate_cred_by_code",
        json={"kind": 1, "code": oauth_code},
        headers={
            "User-Agent": UA,
            "Content-Type": "application/json",
            "platform": "1",
            "v-name": "1.0.0",
        },
        timeout=20,
    ) as r:
        j = await r.json(content_type=None)
        if j.get("code") != 0:
            raise RuntimeError(f"换取 cred 失败：{j.get('message')}")
        data = j["data"]
        return data["cred"], str(data.get("token") or data["cred"])


# ---------------------------------------------------------------- 自动续期
#
# 为什么要有这一段
# ----------------
# cred 大约两天就失效。之前每次失效都得手动重登，很烦。
# 但换 cred 用的「通行证 token」有效期长得多 —— 把它存下来，
# 每次 cred 失效时自动换一个新的，就不需要人管了。
#
# 前提：登录时必须把通行证 token 一起存进 skland_full.json 的 hyp_token 字段。
#       老凭据没有这个字段，所以第一次仍要重登一次。

HYP_FILE = _STATE / "skland_hyp.bin"


def save_hyp_token(token: str) -> None:
    """把通行证 token 加密存下来，供日后自动续期用。"""
    try:
        from status.providers import dpapi_encrypt

        HYP_FILE.parent.mkdir(parents=True, exist_ok=True)
        HYP_FILE.write_bytes(dpapi_encrypt(token))
    except Exception:
        pass


def load_hyp_token() -> str:
    """读通行证 token。没有就返回空串。"""
    # 优先从完整凭据里读（登录脚本会写这里）
    if FULL_FILE.exists():
        try:
            obj = json.loads(FULL_FILE.read_text(encoding="utf-8"))
            t = str(obj.get("hyp_token", "")).strip()
            if t:
                return t
        except Exception:
            pass
    if HYP_FILE.exists():
        try:
            return dpapi_decrypt_here(HYP_FILE.read_bytes()).strip()
        except Exception:
            pass
    return ""


def save_cred(cred: str, token: str, user_id: str = "") -> None:
    """续期成功后写回凭据文件，保持 hyp_token 不丢。"""
    obj: dict[str, Any] = {}
    if FULL_FILE.exists():
        try:
            obj = json.loads(FULL_FILE.read_text(encoding="utf-8"))
        except Exception:
            obj = {}
    obj["cred"] = cred
    obj["token"] = token
    if user_id:
        obj["userId"] = user_id
    try:
        FULL_FILE.parent.mkdir(parents=True, exist_ok=True)
        FULL_FILE.write_text(
            json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        pass
    try:
        from status.providers import dpapi_encrypt

        CRED_FILE.write_bytes(dpapi_encrypt(cred))
    except Exception:
        pass


async def refresh_cred() -> tuple[str, str] | None:
    """用通行证 token 换一个新 cred。成功返回 (cred, token)，失败返回 None。"""
    import aiohttp

    hyp = load_hyp_token()
    if not hyp:
        return None
    try:
        async with aiohttp.ClientSession() as session:
            cred, token = await get_cred(session, hyp)
        save_cred(cred, token)
        return cred, token
    except Exception:
        return None


async def ensure_cred() -> tuple[str, str] | None:
    """拿一份「现在能用」的凭据。不能用就先续期，续不上再返回旧的让人看到报错。

    为什么要在读取前主动做，而不是等 binding 失败后再补救：
    binding 的重试带退避（3s、6s），三次失败再续期，一次读取要白等十来秒。
    而且期间状态面板已经先显示了一次「读取失败」，用户看到的是错误，
    哪怕几秒后自愈了。主动检查能把这段时间省掉。
    """
    creds = load_credentials()
    if not creds:
        return None
    cred, token = creds

    # 用 user/check 探一下 —— 这个接口不校验签名，只看 cred 本身是否还有效，
    # 正好拿来当「过期没有」的探针。
    alive = False
    try:
        import aiohttp

        async with aiohttp.ClientSession() as session:
            headers = {**_random_headers(), "cred": cred, "platform": PLATFORM, "vName": VNAME}
            async with session.get(
                f"{ZONAI}/api/v1/user/check", headers=headers, timeout=10
            ) as r:
                j = await r.json(content_type=None)
                alive = j.get("code") == 0
    except Exception:
        # 网络抖一下就当作「不确定」，直接用原来的凭据往下走，
        # 不因为它失败就贸然续期（续期本身也要联网）。
        return creds

    if alive:
        return creds

    fresh = await refresh_cred()
    return fresh or creds


async def get_binding(
    session: aiohttp.ClientSession, cred: str, token: str = "", retries: int = 3
) -> list[dict[str, Any]]:
    """绑定角色。

    返回 401「请求异常」有两种可能，需要分开处理：
      1. 真的被限流 —— 隔几秒重试就好（这接口限流确实严）
      2. cred 过期了 —— 重试多少次都没用，必须换新的

    区分办法：先按限流重试；如果全都失败，就试着用通行证 token
    换一个新 cred 再打一次。有 hyp_token 的话这一步能让程序自愈，
    不需要人去点重新登录。
    """
    path = "/api/v1/game/player/binding"
    last = ""

    async def _once(c: str, t: str) -> dict[str, Any]:
        headers, _ = _make_sign(c, path, "", token=t)
        async with session.get(f"{ZONAI}{path}", headers=headers, timeout=20) as r:
            return await r.json(content_type=None)

    for attempt in range(retries):
        j = await _once(cred, token)
        if j.get("code") == 0:
            return j.get("data", {}).get("list", [])
        last = str(j.get("message", j.get("code")))
        if attempt < retries - 1:
            await asyncio.sleep(3 * (attempt + 1))

    # 重试都失败了 —— 有可能是 cred 过期，试着自动续期一次
    fresh = await refresh_cred()
    if fresh:
        new_cred, new_token = fresh
        j = await _once(new_cred, new_token)
        if j.get("code") == 0:
            return j.get("data", {}).get("list", [])
        last = str(j.get("message", j.get("code")))

    raise RuntimeError(
        f"读取绑定角色失败（已重试 {retries} 次）：{last}"
        + ("" if load_hyp_token() else "；且没有存通行证 token，无法自动续期，请重新登录")
    )


async def get_player_info(
    session: aiohttp.ClientSession, cred: str, uid: str, token: str = ""
) -> dict[str, Any]:
    """明日方舟。注意签名要把 query 一起算进去。"""
    path = "/api/v1/game/player/info"
    query = f"uid={uid}"
    headers, _ = _make_sign(cred, path, query, token=token)
    async with session.get(
        f"{ZONAI}{path}", params={"uid": uid}, headers=headers, timeout=25
    ) as r:
        j = await r.json(content_type=None)
        if j.get("code") != 0:
            raise RuntimeError(f"读取方舟数据失败：{j.get('message')}")
        return j.get("data", {})


async def get_endfield_card(
    session: aiohttp.ClientSession, cred: str, role_id: str, server_id: str,
    token: str = "",
) -> dict[str, Any]:
    """终末地完整数据卡：理智、每日任务、通行证。

    Header 要额外带 `sk-game-role: 3_{roleId}_{serverId}`。
    """
    path = "/api/v1/game/endfield/card/detail"
    query = f"roleId={role_id}&serverId={server_id}"
    headers, _ = _make_sign(cred, path, query, token=token)
    headers["sk-game-role"] = f"3_{role_id}_{server_id}"
    async with session.get(
        f"{ZONAI}{path}",
        params={"roleId": role_id, "serverId": server_id},
        headers=headers,
        timeout=30,
    ) as r:
        j = await r.json(content_type=None)
        if j.get("code") != 0:
            raise RuntimeError(f"读取终末地数据失败：{j.get('message')}")
        return j.get("data", {})


def summarize(data: dict[str, Any]) -> dict[str, Any]:
    """从 player/info 的大 JSON 里提取面板要用的字段。"""
    status = data.get("status", {}) or {}
    ap = status.get("ap", {}) or {}
    routine = data.get("routine", {}) or {}

    daily = routine.get("daily", {}) or {}
    weekly = routine.get("weekly", {}) or {}

    campaign = data.get("campaign", {}) or {}
    reward = campaign.get("reward", {}) or {}

    hire = (data.get("building", {}) or {}).get("hire", {}) or {}

    return {
        "nick": status.get("name", ""),
        "level": status.get("level"),
        "ap_current": ap.get("current"),
        "ap_max": 135,
        "daily_done": daily.get("current"),
        "daily_max": daily.get("total"),
        "weekly_done": weekly.get("current"),
        "weekly_max": weekly.get("total"),
        "campaign_done": reward.get("current"),
        "campaign_max": reward.get("total"),
        "hire_refresh": hire.get("refreshCount"),
        "register_ts": status.get("registerTs"),
    }
