# -*- coding: utf-8 -*-
"""多账号凭据管理。

每个米游社账号存成一个文件 `.dsh/accounts/<uid>.bin`（DPAPI 加密）。
`.dsh/active_account` 记录当前用哪个。

星铁在另一个号上的话，登两次就各有一份，面板会一起显示。
"""
from __future__ import annotations

import json
from pathlib import Path

from status.providers import dpapi_decrypt, dpapi_encrypt

from status.paths import data_dir as _data_dir, find_state_dir

WORK = _data_dir()
_STATE = find_state_dir()
ACCOUNT_DIR = _STATE / "accounts"
ACTIVE_FILE = _STATE / "active_account"
LEGACY_FILE = _STATE / "mihoyo_cookies.bin"


def _ensure_dir() -> None:
    ACCOUNT_DIR.mkdir(parents=True, exist_ok=True)


def save_account(cookies: dict[str, str]) -> str:
    """保存一个账号，返回账号 ID。"""
    _ensure_dir()
    uid = str(cookies.get("account_id_v2") or cookies.get("ltuid_v2") or "unknown")
    target = ACCOUNT_DIR / f"{uid}.bin"
    target.write_bytes(dpapi_encrypt(json.dumps(cookies, ensure_ascii=False)))
    if not ACTIVE_FILE.exists():
        ACTIVE_FILE.write_text(uid, encoding="utf-8")
    return uid


def list_accounts() -> list[str]:
    """列出已保存的账号 ID。"""
    if not ACCOUNT_DIR.exists():
        return []
    return sorted(p.stem for p in ACCOUNT_DIR.glob("*.bin"))


def load_account(uid: str) -> dict[str, str] | None:
    f = ACCOUNT_DIR / f"{uid}.bin"
    if not f.exists():
        return None
    try:
        return json.loads(dpapi_decrypt(f.read_bytes()))
    except Exception:
        return None


def active_uid() -> str | None:
    if ACTIVE_FILE.exists():
        v = ACTIVE_FILE.read_text(encoding="utf-8").strip()
        if v:
            return v
    accounts = list_accounts()
    return accounts[0] if accounts else None


def set_active(uid: str) -> None:
    ACTIVE_FILE.write_text(uid, encoding="utf-8")


def load_all_accounts() -> dict[str, dict[str, str]]:
    """所有账号的 cookie，键是 uid。会自动把旧版单文件迁移进来。"""
    _ensure_dir()

    # 迁移旧版
    if LEGACY_FILE.exists() and not list_accounts():
        try:
            old = json.loads(dpapi_decrypt(LEGACY_FILE.read_bytes()))
            save_account(old)
        except Exception:
            pass

    out: dict[str, dict[str, str]] = {}
    for uid in list_accounts():
        c = load_account(uid)
        if c:
            out[uid] = c
    return out
