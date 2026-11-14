# -*- coding: utf-8 -*-
"""检查各工具是否有新版本。

设计取舍
--------
判据分两层，先本地后联网：

1. 本地读 exe 的文件版本号 —— 几毫秒，不联网。
2. 只有需要时，才去 GitHub API 拿最新 tag —— 网络请求，慢。

这样「检查」这一步本身很快；真正花时间的只有「确实有新版本、要去下载」的时候。

各家更新方式不同，所以 CheckResult 里记了 kind：
    "exe"     —— 有独立更新器，运行它即可
    "install" —— 需要运行安装器
    "self"    —— 没有独立更新器，靠主程序自己在启动时检查
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

TIMEOUT = 8  # 联网查 GitHub 的超时（秒）


@dataclass
class Tool:
    key: str
    name: str
    exe: str                 # 主程序，用来读本地版本
    updater: str = ""        # 更新器，留空表示没有独立更新器
    kind: str = "self"       # exe / install / self
    repo: str = ""           # GitHub repo，用来查最新版本
    tag_prefix: str = ""     # 有的 tag 带 v，有的不带
    version_file: str = ""   # 读不到 exe 版本时，从这里读
    version_json_key: str = ""  # version_file 是 json 时，指定取哪个键
    git_dir: str = ""        # 再不行，从 git tag 推断（源码部署的工具）
    mirror_rid: str = ""     # 走 Mirror 酱的工具，填它的资源 id


TOOLS: list[Tool] = [
    Tool(
        key="maa",
        name="明日方舟 · MAA",
        exe=r"A:\MAA\MAA.exe",
        updater=r"A:\MAA\MAA.Updater.exe",
        kind="exe",
        repo="MaaAssistantArknights/MaaAssistantArknights",
        tag_prefix="v",
    ),
    Tool(
        key="bettergi",
        name="原神 · BetterGI",
        exe=r"A:\BetterGI\BetterGI.exe",
        updater=r"A:\BetterGI\BetterGI.update.exe",
        kind="exe",
        repo="babalae/better-genshin-impact",
        tag_prefix="v",
    ),
    Tool(
        key="maaend",
        name="终末地 · MaaEnd",
        exe=r"A:\MaaEnd\MaaEnd.exe",
        kind="self",          # 没有独立更新器，启动时自检
        repo="MaaEnd/MaaEnd",
        tag_prefix="v",
        # 注意：MaaEnd.exe 的 FileVersion 是内置框架版本（2.8.0），
        # 不是 MaaEnd 自己的版本。真版本在 interface.json 里，所以优先读它。
        version_file=r"A:\MaaEnd\interface.json",
        version_json_key="version",
    ),
    Tool(
        key="zzz",
        name="绝区零 · 一条龙",
        exe=r"A:\ZZZ\ZZZ-auto\OneDragon-Launcher.exe",
        updater=r"A:\ZZZ\ZZZ-auto\OneDragon-Installer.exe",
        kind="install",       # 跑安装器更新
        # 这个 exe 没有内嵌版本，只能从 git tag 读
        git_dir=r"A:\ZZZ\ZZZ-auto",
        repo="OneDragon-Anything/ZenlessZoneZero-OneDragon",
        tag_prefix="v",
    ),
    Tool(
        key="m7a",
        name="星铁 · March7th",
        exe=r"A:\March7thAssistant_full\March7th Assistant.exe",
        updater=r"A:\March7thAssistant_full\March7th Updater.exe",
        kind="exe",
        repo="moesnow/March7thAssistant",
        tag_prefix="v",
        # 这个 exe 也没有内嵌版本
        version_file=r"A:\March7thAssistant_full\assets\config\version.txt",
    ),
]


@dataclass
class CheckResult:
    tool: Tool
    local: str = ""
    latest: str = ""
    status: str = "unknown"      # current / outdated / unknown / missing
    note: str = ""
    can_auto: bool = False

    @property
    def needs_action(self) -> bool:
        return self.status == "outdated"


# ---------------------------------------------------------------- 本地版本
def local_version(exe: Path) -> str:
    """读 Windows exe 的内嵌版本号。

    直接用 Win32 版本 API，不走 PowerShell —— 后者每读一个文件要 1 秒多，
    五个工具就是七秒，太慢了。这里五个加起来约 1 毫秒。
    """
    if not exe.exists():
        return ""
    try:
        import ctypes
        from ctypes import wintypes

        size = ctypes.windll.version.GetFileVersionInfoSizeW(str(exe), None)
        if not size:
            return ""
        buf = ctypes.create_string_buffer(size)
        if not ctypes.windll.version.GetFileVersionInfoW(str(exe), 0, size, buf):
            return ""

        ptr = ctypes.c_void_p()
        length = wintypes.UINT()
        if not ctypes.windll.version.VerQueryValueW(
            buf, r"\VarFileInfo\Translation", ctypes.byref(ptr), ctypes.byref(length)
        ):
            return ""
        if not length.value:
            return ""

        # 语言/代码页对，取第一组
        trans = ctypes.cast(ptr, ctypes.POINTER(ctypes.c_ushort))
        lang, codepage = trans[0], trans[1]

        sub = f"\\StringFileInfo\\{lang:04x}{codepage:04x}\\FileVersion"
        if not ctypes.windll.version.VerQueryValueW(
            buf, sub, ctypes.byref(ptr), ctypes.byref(length)
        ):
            return ""
        if not length.value:
            return ""

        raw = ctypes.wstring_at(ptr, length.value)
        return raw.strip().rstrip("\x00").strip()
    except Exception:
        return ""


def _version_from_file(path: str, json_key: str = "") -> str:
    try:
        p = Path(path)
        if not p.exists():
            return ""
        text = p.read_text(encoding="utf-8-sig")
        if json_key:
            data = json.loads(text)
            return str(data.get(json_key, "")).strip()
        return text.strip()
    except Exception:
        return ""


def _version_from_git(git_dir: str) -> str:
    """源码部署的工具（如绝区零一条龙）的版本。

    注意：不要用 `git describe --tags`。
    一条龙这类工具是滚动更新的，代码天天变但 tag 不一定跟。
    实测：本地 HEAD 是 33cfa5a（11月2日），最近的 tag 却还停在 v2.5.6，
    于是它被误判成「落后于 v2.6.0」，而实际上本地代码比 v2.6.0 还新。

    改用「提交短号 + 日期」，跟界面上显示的一致，也不会骗人。
    """
    try:
        if not (Path(git_dir) / ".git").exists():
            return ""
        out = subprocess.run(
            ["git", "log", "-1", "--format=%h %cs"],
            cwd=git_dir, capture_output=True, text=True, timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return (out.stdout or "").strip()
    except Exception:
        return ""


def _git_last_commit_date(git_dir: str) -> str:
    """本地仓库最后一次提交的日期（YYYY-MM-DD）。"""
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%cs"],
            cwd=git_dir, capture_output=True, text=True, timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return (out.stdout or "").strip()
    except Exception:
        return ""


def _git_tag_commit_date(git_dir: str, tag: str) -> str:
    """线上那个 tag 指向的提交日期。本地仓库里查不到就返回空。"""
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%cs", tag],
            cwd=git_dir, capture_output=True, text=True, timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return (out.stdout or "").strip()
    except Exception:
        return ""


def detect_local(tool: Tool) -> str:
    """按优先级取本地版本。

    有 version_file 的先读它 —— 这类工具的 exe 版本号不可靠
    （MaaEnd.exe 的 FileVersion 是内置框架版本，不是工具本身版本）。
    然后才是 exe 内嵌版本，最后是 git tag。
    """
    if tool.version_file:
        v = _version_from_file(tool.version_file, tool.version_json_key)
        if v:
            return v
    v = local_version(Path(tool.exe))
    if v:
        return v
    if tool.git_dir:
        v = _version_from_git(tool.git_dir)
        if v:
            return v
    return ""


# ---------------------------------------------------------------- 线上版本
def _norm(tag: str) -> str:
    return tag.strip().lstrip("vV")


def latest_version(tool: Tool) -> tuple[str, str]:
    """查最新版本。返回 (版本, 错误信息)。"""
    if tool.mirror_rid:
        return _latest_from_mirror(tool.mirror_rid)
    if not tool.repo:
        return "", "没有配置版本来源"
    return _latest_from_github(tool.repo)


def _latest_from_mirror(rid: str) -> tuple[str, str]:
    """查 Mirror 酱。不带 CDK 也能读到版本号（仅用于比较，不下载）。"""
    for host in ("https://mirrorchyan.com", "https://mirrorchyan.net"):
        url = f"{host}/api/resources?rid={rid}&os=windows&arch=x64&channel=stable"
        req = urllib.request.Request(url, headers={"User-Agent": "Ripples-VersionCheck"})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            d = data.get("data") or {}
            ver = str(d.get("version_name") or d.get("version") or "")
            if ver:
                return ver.strip(), ""
            return "", str(data.get("msg") or "返回里没有版本号")
        except urllib.error.HTTPError as exc:
            last = f"HTTP {exc.code}"
        except urllib.error.URLError as exc:
            last = f"网络不可用：{exc.reason}"
        except Exception as exc:
            last = str(exc)
    return "", last


def _latest_from_github(repo: str) -> tuple[str, str]:
    """查 GitHub 最新 tag。

    踩过的坑：匿名调 api.github.com 每小时只有 60 次配额，
    反复点几下就 403。所以优先走 releases/latest 的跳转地址，
    它不占 API 配额；实在拿不到才退回 API。
    """
    # 路线一：不跟随跳转，从 Location 头里读 tag
    try:
        url = f"https://github.com/{repo}/releases/latest"
        req = urllib.request.Request(url, headers={"User-Agent": "Ripples-VersionCheck"})

        class _NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *a, **kw):
                return None

        opener = urllib.request.build_opener(_NoRedirect)
        loc = ""
        try:
            with opener.open(req, timeout=TIMEOUT) as resp:
                loc = resp.headers.get("Location", "")
        except urllib.error.HTTPError as exc:
            if exc.headers:
                loc = exc.headers.get("Location", "")
        if loc:
            tag = loc.rstrip("/").rsplit("/", 1)[-1]
            if tag:
                return _norm(tag), ""
    except Exception:
        pass

    # 路线二：退回 API
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Ripples-VersionCheck",
        "Accept": "application/vnd.github+json",
    })
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        tag = str(data.get("tag_name") or "")
        return _norm(tag), ""
    except urllib.error.HTTPError as exc:
        if exc.code == 403:
            return "", "GitHub 限流，稍后再试"
        return "", f"HTTP {exc.code}"
    except urllib.error.URLError as exc:
        return "", f"网络不可用：{exc.reason}"
    except Exception as exc:
        return "", str(exc)


# ---------------------------------------------------------------- 比对
def _cmp(a: str, b: str) -> int:
    """比较版本号。a>b 返回 1，a<b 返回 -1，相等 0。无法比较返回 0。"""
    def parts(s: str) -> list[int]:
        return [int(x) for x in re.findall(r"\d+", s)]

    pa, pb = parts(a), parts(b)
    if not pa or not pb:
        return 0
    n = max(len(pa), len(pb))
    pa += [0] * (n - len(pa))
    pb += [0] * (n - len(pb))
    for x, y in zip(pa, pb):
        if x != y:
            return 1 if x > y else -1
    return 0


def check_one(tool: Tool, online: bool = True) -> CheckResult:
    res = CheckResult(tool=tool)
    exe = Path(tool.exe)

    if not exe.exists():
        res.status = "missing"
        res.note = f"找不到 {exe}"
        return res

    res.local = detect_local(tool)
    res.can_auto = bool(tool.updater and Path(tool.updater).exists())

    if not online or not tool.repo:
        res.status = "unknown"
        res.note = "无法联网比对，仅显示本地版本" if not tool.repo else "未检查"
        return res

    latest, err = latest_version(tool)
    if err:
        res.status = "unknown"
        res.note = f"查询失败：{err}"
        return res

    res.latest = latest
    if not res.local:
        res.status = "unknown"
        res.note = "读不到本地版本"
        return res

    # git 部署的工具走日期比较，不比较版本号。
    # 这类工具有 tag 不跟代码走的问题，比版本号必然误判。
    if tool.git_dir:
        local_date = _git_last_commit_date(tool.git_dir)
        if local_date:
            tag_date = _git_tag_commit_date(tool.git_dir, f"v{latest}")
            if not tag_date:
                tag_date = _git_tag_commit_date(tool.git_dir, latest)
            if tag_date and local_date >= tag_date:
                res.status = "current"
                res.note = f"本地提交 {local_date} ≥ 最新版 {tag_date}"
                return res
            if tag_date:
                res.status = "outdated"
                res.note = f"本地 {local_date} < 最新版 {tag_date}"
                return res
            # 本地仓库里没有那个 tag，退回按版本号比
        # 日期拿不到时继续往下走

    c = _cmp(res.local, latest)
    if c < 0:
        res.status = "outdated"
        res.note = f"本地 {res.local} → 最新 {latest}"
    else:
        res.status = "current"
        res.note = "已是最新"
    return res


def check_all(online: bool = True) -> list[CheckResult]:
    """检查全部工具。联网时并发查询，避免一个个等。

    实测：三家并发约 1.3 秒，串行要 4 秒以上。
    """
    if not online:
        return [check_one(t, online=False) for t in TOOLS]

    # 有仓库的才联网，没仓库的本地判断就够了
    online_tools = [t for t in TOOLS if (t.repo or t.mirror_rid)]
    offline_tools = [t for t in TOOLS if not (t.repo or t.mirror_rid)]

    results: dict[str, CheckResult] = {}
    if online_tools:
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=len(online_tools)) as ex:
            for r in ex.map(lambda t: check_one(t, online=True), online_tools):
                results[r.tool.key] = r
    for t in offline_tools:
        r = check_one(t, online=False)
        results[r.tool.key] = r

    # 保持 TOOLS 的原始顺序
    return [results[t.key] for t in TOOLS if t.key in results]


def format_report(results: list[CheckResult]) -> str:
    lines = []
    for r in results:
        mark = {
            # 只用 GBK 能编码的符号：cmd 默认代码页 936，U+2713/U+2717 会抛 UnicodeEncodeError
            "current": "√",
            "outdated": "↑",
            "missing": "×",
            "unknown": "?",
        }.get(r.status, "?")
        auto = "可自动更新" if r.can_auto else "需手动"
        ver = f"{r.local or '-'}"
        if r.latest:
            ver += f" / 最新 {r.latest}"
        lines.append(f"  {mark} {r.tool.name:<20} {ver:<24} {r.note}  [{auto}]")
    return "\n".join(lines)


def run_updater(tool: Tool) -> tuple[bool, str]:
    """启动该工具的更新器。返回 (是否启动成功, 说明)。"""
    if not tool.updater:
        return False, "没有独立更新器"
    p = Path(tool.updater)
    if not p.exists():
        return False, f"找不到 {p}"
    try:
        subprocess.Popen([str(p)], cwd=str(p.parent))
        return True, f"已启动 {p.name}"
    except Exception as exc:
        return False, f"启动失败：{exc}"


if __name__ == "__main__":
    online = "--offline" not in sys.argv
    print(f"检查更新（{'联网' if online else '仅本地'}）\n")
    rs = check_all(online=online)
    print(format_report(rs))
    need = [r for r in rs if r.needs_action]
    print()
    if need:
        print(f"{len(need)} 个需要更新")
        for r in need:
            auto = "可自动" if r.can_auto else "需手动"
            print(f"  - {r.tool.name}（{auto}）")
    else:
        print("全部为最新，或无法判断")
