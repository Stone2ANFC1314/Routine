# -*- coding: utf-8 -*-
"""PyInstaller 打包配置。

用法（在项目根执行）：

    .venv\\Scripts\\python.exe -m PyInstaller build_exe.spec --noconfirm

产物：
    dist\\游戏日常\\游戏日常.exe        目录版（推荐，启动快）
    整个 dist\\游戏日常\\ 文件夹就是可分发的东西

为什么用「目录版」不用「单文件」
    单文件模式每次启动都要把 100+ MB 解包到临时目录，第一次启动要好几秒；
    目录版直接读，秒开。游戏日常工具是每天要开的东西，这几秒很值钱。

打包进去什么、不打包什么
    带：assets/（界面素材）、status/（状态读取）、tools/（更新检查）、
        Anigame-script-manager/ 全部代码
    不带：原图目录（19MB 官方素材，开会话时不该分发）、logs、
        runtime_stats、__pycache__、.venv
"""
from pathlib import Path

ROOT = Path(SPECPATH).resolve()          # 项目根
APP = ROOT / "Anigame-script-manager"    # 程序目录

# ---- 数据文件 ----
# 只带「程序真的会读」的素材。原图目录有 19MB 官方美术资源，
# 打包分发出去不合适（版权），而且程序只用到其中几张。
CYRENE = ROOT / "assets" / "cyrene"

# 「加工」目录里混着大量早期制作过程的中间图（_grid.png、_souls_all.png
# 这类以下划线开头的），程序一个都不读。逐个列出真正需要的，
# 不要整个目录打包——那会带进 8MB 多的废图。
NEEDED_PROCESSED = [
    "logo-trim.png",
    "signature.png",
    "p-side.png",
    "p-half.png",
    "p-side-heart.png",
    "heart_reading.png",
    # 应用图标。漏了这个的话，窗口和任务栏会退回到 ripples.ico
    # （她眼睛的特写），跟 exe 上那个星魂4 图标不是同一张。
    "app-icon.ico",
    "ripples.ico",
]

datas = [
    (str(CYRENE / "加工" / name), "assets/cyrene/加工")
    for name in NEEDED_PROCESSED
    if (CYRENE / "加工" / name).exists()
]
datas += [
    # 原图里程序会用到的那几张
    *[
        (str(CYRENE / "原图" / name), "assets/cyrene/原图")
        for name in (
            "art-reading.png",
            "art-starry.jpg",
            "星魂1.png",
            "星魂3.png",
            "星魂4.png",
            "logo-official.png",
        )
        if (CYRENE / "原图" / name).exists()
    ],
]

# 美图画廊：Cyrene/ 目录整包带上。
#
# 这和 .gitignore 里排除 Cyrene/ 不冲突 —— 那边管的是「不往公开仓库推」
# （190 MB 的二次元插画，版权不属于本项目），这边管的是「打给自己用的
# exe 里要有这些图」。两件事互不影响。
#
# 目录体积较大（约 190 MB），介意的话可以把 GALLERY_INCLUDE 设成 False，
# 画廊会显示「没找到图片」，其余功能不受影响。
GALLERY_INCLUDE = True
GALLERY_DIR = ROOT / "Cyrene"
if GALLERY_INCLUDE and GALLERY_DIR.is_dir():
    datas += [(str(GALLERY_DIR), "Cyrene")]

# 图标：用星魂4 生成的 app-icon.ico（多尺寸）。
#
# 以前这里优先用项目根的 app.ico —— 那是另一个角色的图，
# 而且只有 256×256 一种尺寸，Windows 在标题栏/任务栏会硬缩导致糊。
# 现在固定用 assets/cyrene/加工/app-icon.ico（由 tools/make_icon.py 生成，
# 带 16/24/32/48/64/128/256 全套尺寸）。
ICON = CYRENE / "加工" / "app-icon.ico"
if not ICON.exists():
    print(f"[build] 警告：找不到图标 {ICON}，将使用 PyInstaller 默认图标")
    print("[build] 先跑：python tools/make_icon.py")
    ICON = None

# 应用名。改了这里，exe 文件名和任务管理器里显示的名字都会变。
APP_NAME = "Ripple"

# 文件属性。不填的话右键「属性 → 详细信息」里是一片空白，
# 资源管理器里也只显示文件名，看着像个来路不明的程序。
# version_info.txt 由下面的代码现场生成，避免多维护一个文件。
VERSION = "1.0.0"
COMPANY = "Ripple"
DESCRIPTION = "游戏日常自动化队列"

_version_info = f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({','.join(VERSION.split('.') + ['0'] * (4 - len(VERSION.split('.'))))}),
    prodvers=({','.join(VERSION.split('.') + ['0'] * (4 - len(VERSION.split('.'))))}),
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '080404B0',
        [StringStruct('CompanyName', '{COMPANY}'),
         StringStruct('FileDescription', '{DESCRIPTION}'),
         StringStruct('FileVersion', '{VERSION}'),
         StringStruct('InternalName', '{APP_NAME}'),
         StringStruct('OriginalFilename', '{APP_NAME}.exe'),
         StringStruct('ProductName', '{APP_NAME}'),
         StringStruct('ProductVersion', '{VERSION}')])
    ]),
    VarFileInfo([VarStruct('Translation', [2052, 1200])])
  ]
)
"""
_version_file = Path(SPECPATH) / "build" / "version_info.txt"
_version_file.parent.mkdir(parents=True, exist_ok=True)
_version_file.write_text(_version_info, encoding="utf-8")

# ---- 隐式导入 ----
# 只列程序运行真正会用到的模块。
#
# 这里吃过一次亏：原来写的是 collect_submodules("status")，
# 把 status/ 下所有文件都收进来了——其中 captcha.py、edge_login.py
# 这几个旧的登录工具 import 了 playwright，于是 102 MB 的
# playwright 浏览器驱动被打进包，而主程序根本不碰它们。
# 逐个列出来，体积从 258 MB 降到一百多。
hiddenimports = [
    # status.paths 是这次补上的：它负责把 .dsh/ 解析到 exe 旁边，
    # 漏了它打包后凭据路径会退回临时目录，游戏状态一条都读不出来。
    "status.paths",
    "status.providers",
    "status.skland",
    "status.logs",
    "status.accounts",
    "status.genshin_widget",
    "update_check",
    "aiohttp",
    "qrcode",
]

a = Analysis(
    [str(APP / "main.py")],
    # pathex 决定 PyInstaller 去哪里找模块。
    #
    # tools/ 必须列进来：update_check.py 在那儿，主程序是按需 import 它的
    # （「检查更新」按钮点了才加载）。不列的话，即使 hiddenimports 里写了
    # "update_check"，PyInstaller 也搜不到文件，打出来的 exe 一点检查更新
    # 就报 "No module named 'update_check'"。
    pathex=[str(ROOT), str(APP), str(ROOT / "tools")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # 排掉用不到又特别大的包，能省不少体积
    excludes=[
        "tkinter", "matplotlib", "scipy", "pandas", "notebook",
        "IPython", "pytest",
        # status/ 里的旧登录工具才用得到，主程序不 import
        "playwright", "PIL",
        "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets",
        "PySide6.QtQml", "PySide6.QtQuick",
        "PySide6.Qt3DCore", "PySide6.QtCharts", "PySide6.QtDataVisualization",
        "PySide6.QtMultimedia", "PySide6.QtQuick3D",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,             # UPX 容易被杀软误报，而且省不了多少
    console=False,         # 窗口程序，不弹黑框
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ICON) if ICON else None,
    version=str(_version_file),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=APP_NAME,
)
