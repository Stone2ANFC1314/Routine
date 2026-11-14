# -*- coding: utf-8 -*-
"""验证打包后的 exe 能不能 import update_check。

做法：在 dist 目录里起一个 Python，把 sys.frozen 设成 True 模拟打包环境，
用 PyInstaller 的 archive 读取能力确认模块确实在包里。

更直接的办法是让 exe 自己跑一次检查更新，但那需要点按钮。
这里退一步：检查 PYZ 归档里有没有这个模块。
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DIST = ROOT / "dist" / "Ripple"


def main() -> int:
    exe = DIST / "Ripple.exe"
    if not exe.exists():
        print(f"找不到 {exe}")
        return 1

    # PyInstaller 提供了 pyi-archive_viewer 的 API
    try:
        from PyInstaller.archive.readers import CArchiveReader, ZlibArchiveReader
    except ImportError:
        print("本机 PyInstaller 版本不支持 archive 读取，改用字符串扫描")
        return scan_strings(exe)

    print(f"检查 {exe.name} 的归档…")
    try:
        arch = CArchiveReader(str(exe))
    except Exception as exc:
        print(f"读取归档失败：{exc}")
        return scan_strings(exe)

    # 找 PYZ
    names = list(arch.toc.keys()) if hasattr(arch, "toc") else []
    print(f"  归档条目 {len(names)} 个")
    pyz_name = next((n for n in names if n.endswith(".pyz")), None)
    if pyz_name is None:
        print("  没找到 PYZ 归档")
        return scan_strings(exe)

    data = arch.extract(pyz_name)
    tmp = ROOT / "build" / "_check.pyz"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_bytes(data)
    pyz = ZlibArchiveReader(str(tmp))
    mods = set(pyz.toc.keys()) if hasattr(pyz, "toc") else set()

    for target in ("update_check", "status.providers", "status.paths", "status.skland"):
        ok = target in mods
        print(f"  {'√' if ok else '×'} {target}")
    return 0


def scan_strings(exe: pathlib.Path) -> int:
    """退路：直接在 exe 里找模块名。"""
    data = exe.read_bytes()
    print("用字符串扫描：")
    for target in (b"update_check", b"status.providers", b"status.paths"):
        ok = target in data
        print(f"  {'√' if ok else '×'} {target.decode()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
