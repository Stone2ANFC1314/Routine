# -*- coding: utf-8 -*-
"""自检：找出「以前踩过、以后别再踩」的代码问题。

为什么要有这个文件
------------------
线上真的发生过：`_run_one_task` 里 `monitor_kind` 在赋值之前被使用，
Python 抛 UnboundLocalError，整个队列只跑完第一个任务就中止，而且
日志里只留一行看不出所以然。

这类问题人工 review 很容易漏，所以写成能自动跑的脚本。只用标准库，
不装任何依赖。

检查项
------
1. 使用早于赋值      同一个函数里，变量在赋值之前被读取
2. 重复定义          同一个作用域里同名的函数/类被定义了两次
3. 可疑的裸 except   except: 吞掉所有异常，连 KeyboardInterrupt 都吞
4. 硬编码敏感值       代码里直接写死手机号/token/cookie

用法
----
    python tools/selfcheck.py            # 检查默认范围
    python tools/selfcheck.py 路径 ...   # 检查指定文件或目录
    python tools/selfcheck.py --strict   # 有警告也返回非 0
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

# 默认要检查的范围（相对仓库根目录）
DEFAULT_TARGETS = [
    "Anigame-script-manager/core",
    # 整个 ui 目录一起查。以前只列 main_window_new.py 和 theme.py，
    # 新加的 splash.py / fonts.py / task_settings.py 都漏在外面，
    # 等于这些文件从来没被自检覆盖过。
    "Anigame-script-manager/ui",
    "Anigame-script-manager/main.py",
    # 这两个和 core 一样是执行链路的一部分，以前也漏在检查范围外
    "Anigame-script-manager/external_watch.py",
    "status",
    # run_queue.py / maa_watch.py / maaend_watch.py 已经不在了：
    # 命令行版入口被 Anigame-script-manager 取代，监控逻辑并入 external_watch.py。
    # 2026-11-10 清理时从检查清单里一并去掉，否则 collect_files 找不到文件会报警告。
]

SKIP_DIR_NAMES = {"__pycache__", ".venv", ".git", "node_modules", "build", "dist"}


class Issue:
    def __init__(self, level: str, path: Path, line: int, code: str, msg: str):
        self.level = level      # "error" / "warning"
        self.path = path
        self.line = line
        self.code = code
        self.msg = msg

    def render(self, root: Path) -> str:
        try:
            rel = self.path.relative_to(root)
        except ValueError:
            rel = self.path
        return f"{self.level.upper():7} {rel}:{self.line}  [{self.code}] {self.msg}"


# ---------------------------------------------------------------- 检查一
def check_use_before_assign(tree: ast.AST, path: Path) -> list[Issue]:
    """找出「函数内先读、后赋值」的局部变量。

    正是 monitor_kind 那类 bug。判断方式：按行号顺序走一遍函数体，
    记录每个名字第一次被「读」和第一次被「写」的位置，若读在写之前
    且该名字在整个函数里确实有赋值（说明是局部变量），就报出来。
    """
    issues: list[Issue] = []

    for func in [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        # nonlocal / global 声明的名字：真正的赋值可能在别的函数或模块层，
        # 这里不做跨作用域分析，直接跳过，避免误报。
        declared_outer: set[str] = set()
        for node in ast.walk(func):
            if isinstance(node, (ast.Nonlocal, ast.Global)):
                declared_outer.update(node.names)

        # 推导式 / 生成器里的循环变量（例如 {k: ... for k, v in ...}）：
        # 它们的赋值和使用发生在同一条表达式内，按行号比较会误报。
        comprehension_targets: set[str] = set()
        for node in ast.walk(func):
            if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
                for gen in node.generators:
                    for sub in ast.walk(gen.target):
                        if isinstance(sub, ast.Name):
                            comprehension_targets.add(sub.id)

        # 收集这个函数作用域内「有赋值」的名字（不含嵌套函数内部的）
        assigned_here: set[str] = set()
        for node in ast.walk(func):
            if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
                assigned_here.add(node.id)
            elif isinstance(node, ast.arg):
                assigned_here.add(node.arg)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node is not func:
                assigned_here.add(node.name)

        skip = declared_outer | comprehension_targets
        assigned_here -= skip

        if not assigned_here:
            continue

        # 按位置排序所有对名字的访问
        events: list[tuple[int, int, str, str]] = []   # (lineno, col, kind, name)
        for node in ast.walk(func):
            if isinstance(node, ast.Name) and node.id not in skip:
                kind = "read" if isinstance(node.ctx, ast.Load) else "write"
                events.append((node.lineno, node.col_offset, kind, node.id))
            elif isinstance(node, ast.arg) and node.arg not in skip:
                events.append((node.lineno, node.col_offset, "write", node.arg))
        events.sort(key=lambda e: (e[0], e[1]))

        first_read: dict[str, int] = {}
        first_write: dict[str, int] = {}
        for lineno, _col, kind, name in events:
            if kind == "read":
                first_read.setdefault(name, lineno)
            else:
                first_write.setdefault(name, lineno)

        for name, read_line in first_read.items():
            if name not in assigned_here:
                continue            # 模块级/全局名，交给运行时
            write_line = first_write.get(name)
            if write_line is not None and read_line < write_line:
                issues.append(Issue(
                    "error", path, read_line, "E001",
                    f"「{name}」在第 {read_line} 行被读取，但直到第 {write_line} 行才赋值"
                    f"（函数 {func.name}）——运行时会抛 UnboundLocalError",
                ))
    return issues


# ---------------------------------------------------------------- 检查二
def check_duplicate_defs(tree: ast.AST, path: Path) -> list[Issue]:
    """同一个作用域里同名的函数/类定义了两次。"""
    issues: list[Issue] = []

    scopes: list[tuple[str, ast.AST]] = [("<module>", tree)]
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            scopes.append((node.name, node))

    for scope_name, scope in scopes:
        seen: dict[str, int] = {}
        body = getattr(scope, "body", [])
        for item in body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if item.name in seen:
                    issues.append(Issue(
                        "warning", path, item.lineno, "W001",
                        f"「{item.name}」在 {scope_name} 里重复定义（上次在第 {seen[item.name]} 行），"
                        f"后一个会覆盖前一个",
                    ))
                else:
                    seen[item.name] = item.lineno
    return issues


# ---------------------------------------------------------------- 检查三
def check_bare_except(tree: ast.AST, path: Path) -> list[Issue]:
    """裸 except: 会连 KeyboardInterrupt / SystemExit 一起吞掉。"""
    issues: list[Issue] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and node.type is None:
            issues.append(Issue(
                "warning", path, node.lineno, "W002",
                "裸 except: 会吞掉包括 KeyboardInterrupt 在内的所有异常，"
                "建议改成 except Exception:",
            ))
    return issues


# ---------------------------------------------------------------- 检查四
SENSITIVE_HINTS = ("138", "139", "150", "151", "152", "158", "159",
                   "186", "187", "188", "189", "176", "177", "178")


def check_hardcoded_secrets(tree: ast.AST, path: Path) -> list[Issue]:
    """代码里直接写死的手机号 / 长 token 字符串。"""
    issues: list[Issue] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        s = node.value.strip()
        # 11 位纯数字且以手机号段开头
        if len(s) == 11 and s.isdigit() and s[:3] in SENSITIVE_HINTS:
            issues.append(Issue(
                "warning", path, node.lineno, "W003",
                "疑似写死的手机号，建议改从配置或环境变量读取",
            ))
        # 32 位十六进制串（token/cred 的典型形状）
        elif len(s) == 32 and all(c in "0123456789abcdefABCDEF" for c in s):
            issues.append(Issue(
                "warning", path, node.lineno, "W004",
                "疑似写死的凭据（32 位十六进制），建议改从文件读取",
            ))
    return issues


# ---------------------------------------------------------------- 驱动
def collect_files(targets: list[Path]) -> list[Path]:
    out: list[Path] = []
    for t in targets:
        if t.is_file():
            if t.suffix == ".py":
                out.append(t)
        elif t.is_dir():
            for p in sorted(t.rglob("*.py")):
                if any(part in SKIP_DIR_NAMES for part in p.parts):
                    continue
                out.append(p)
    return out


def main(argv: list[str]) -> int:
    strict = "--strict" in argv
    args = [a for a in argv if not a.startswith("--")]

    repo_root = Path(__file__).resolve().parent.parent
    if args:
        targets = [Path(a).resolve() for a in args]
    else:
        targets = [repo_root / t for t in DEFAULT_TARGETS]

    files = collect_files(targets)
    if not files:
        print("没有找到可检查的 .py 文件")
        print("目标:", ", ".join(str(t) for t in targets))
        return 2

    all_issues: list[Issue] = []
    parse_errors = 0
    for f in files:
        try:
            # utf-8-sig：有些文件被编辑器加了 BOM，按纯 utf-8 读会解析失败
            src = f.read_text(encoding="utf-8-sig")
            tree = ast.parse(src, filename=str(f))
        except SyntaxError as exc:
            print(f"SYNTAX  {f}:{exc.lineno}  {exc.msg}")
            parse_errors += 1
            continue
        except Exception as exc:
            print(f"READ    {f}  {exc}")
            parse_errors += 1
            continue

        all_issues += check_use_before_assign(tree, f)
        all_issues += check_duplicate_defs(tree, f)
        all_issues += check_bare_except(tree, f)
        all_issues += check_hardcoded_secrets(tree, f)

    errors = [i for i in all_issues if i.level == "error"]
    warnings = [i for i in all_issues if i.level == "warning"]

    print(f"检查了 {len(files)} 个文件\n")
    for issue in errors + warnings:
        print("  " + issue.render(repo_root))

    if not all_issues and not parse_errors:
        # 用 GBK 能编出来的 "√"：cmd 默认代码页 936，U+2713 会让 print 直接抛异常
        print("  没有发现问题 √")

    print()
    print(f"结果：{len(errors)} 个错误，{len(warnings)} 个警告，{parse_errors} 个无法解析")

    if errors or parse_errors:
        return 1
    if strict and warnings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
