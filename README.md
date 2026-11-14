# Ripple · 涟漪

把每天重复的游戏日常自动化掉，点一次就开始，跑完就不用管了。

一个 Windows 桌面小工具：把若干现成的游戏自动化工具排成一条队列，按顺序启动、
等它们各自跑完、再处理下一个。原神、终末地、绝区零、崩铁、明日方舟。

> 「做这个是为了每日重复的无聊的日常不用自己做，然后轻松。」

**下载即用**：去 [Releases](../../releases) 拿 `Ripple-x.x.x.zip`，解压双击 `Ripple.exe`。
不需要装 Python，不需要配环境。

---

## 它做的事

- **排队启动**：拖拽排序，一次点「开始执行」跑完整条队列
- **等待真实结束**：不是睡固定秒数，而是盯进程 / 盯日志判断任务真的完了
- **超时可调**：每个任务单独设最大运行时间，填 0 表示不限制
- **结束后操作**：关游戏、关工具、退模拟器、锁屏、睡眠、休眠、关机，可多选
- **今日状态**：从米游社 / 森空岛读各游戏的体力与日常进度，一屏看完
- **画廊**：翻翻图片，目录可配置

## 它不做的事

- **不代替你设置各游戏工具**。副本打哪个、体力怎么花，都在各自工具里配。
  这里只管「什么时候启动、什么时候算结束」。
- **不修改游戏**，不注入、不读内存。全靠调用现成的开源工具。
- **不做「清没清」的判断**，只把数据摊出来让你自己看。

---

## 系统要求

- Windows 10 / 11（64 位）
- **管理员权限**（模拟键鼠操作必需）
- 上面列出的那些游戏自动化工具需要你自己装好

---

## 支持的自动化工具

| 游戏 | 工具 | 说明 |
|---|---|---|
| 原神 | [BetterGI](https://github.com/babalae/better-genshin-impact) | `startOneDragon` 参数启动一条龙 |
| 终末地 | [MaaEnd](https://github.com/MaaXYZ/MaaEnd) | 通过游戏进程是否关闭判断完成 |
| 绝区零 | [绝区零一条龙](https://github.com/OneDragon-Anything/ZenlessZoneZero-OneDragon) | `-o -c` 运行后关闭游戏 |
| 崩坏：星穹铁道 | [三月七小助手](https://github.com/moesnow/March7thAssistant) | `m7a.exe main --after-finish None` |
| 明日方舟 | [MAA](https://github.com/MaaAssistantArknights/MaaAssistantArknights) | 启动后不等待 |

**这些工具都不随本仓库分发，需要你自己安装。**

---

## 开始使用

### 方式一：直接下载 exe（推荐，不需要装 Python）

去 [Releases](../../releases) 页面下载最新的 `Ripple-x.x.x.zip`，解压后双击 `Ripple.exe`。

**必须用管理员权限运行**——BetterGI 这类工具要模拟键鼠操作，没有管理员权限会失败。
右键 `Ripple.exe` → 「以管理员身份运行」。

解压后的结构：

```
Ripple\
├── Ripple.exe        双击这个
├── config.json       首次启动自动生成
└── _internal\        程序依赖，不要删
```

**整个文件夹要一起拷走，单独拿 exe 是跑不起来的。**

### 方式二：从源码运行（开发者）

需要 Python 3.10 或更高版本。

```bat
git clone https://github.com/Stone2ANFC1314/Routine.git
cd Routine
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

然后双击 `打开界面.bat`，或者：

```bat
.venv\Scripts\python.exe Anigame-script-manager\main.py
```

---

## 第一次打开做什么

### 1. 配置各工具的路径

首次启动会填入一份默认任务清单（原神 / 终末地 / 绝区零 / 星铁 / 明日方舟），
里面的路径是按常见安装位置猜的，**需要你改成自己机器上的实际路径**。

点每个任务右侧的「设置」，或者点「浏览…」选文件。

路径对不对会在任务行上提示：填错的话那一行会显示「脚本不存在」。

### 2. 确认任务的执行方式

每个任务都能单独设置：

| 设置项 | 说明 |
|---|---|
| 最大运行时间 | 超时就按下面的方式处理。**填 0 表示不限时** |
| 到时间后 | 强制结束并继续 / 不结束跳过 / 停止全部 |
| 等待方式 | 什么时候算这个任务跑完了 |
| 后台并行 | 启动后队列继续，不等它结束 |

**等待方式怎么选**：

- `direct_process`（默认）——等进程退出。适合跑完会自己关的
- `fire_and_continue`——启动后不管。适合 MAA 这种自己会结束的
- 其他两种按窗口标题 / 命令行关键词判断

### 3. 拖拽调整顺序

按住左边的把手拖动，**顺序会影响执行结果**：

用 pyautogui 操作前台键鼠的工具（BetterGI、一条龙、M7A）不能同时跑，
会让它们抢输入。所以「启动后不等待」的任务（比如 MAA）要放在最后。

### 4. 选「结束后操作」

底栏的「结束后：xxx」按钮，点开是一个多选面板：

- 关闭星铁（M7A 不会自己关游戏，其他工具会自动关）
- 退出模拟器
- 关闭本次启动的工具
- 锁屏 / 睡眠 / 休眠 / 关机

**这些是整个队列跑完之后才执行的**，不是单个任务结束时。

关机有延迟（默认 60 秒），期间可以取消；人不在的话到点会关。

---

## 关于主题和素材

程序默认用「简约」主题，**不需要任何图片素材**，开箱即用。

界面里还有几套粉色主题（主题名：昔涟），但它们依赖《崩坏：星穹铁道》的官方美术图。
这些图**不随程序分发**（版权属于米哈游），想用的话需要自己准备：

1. 把 `art-reading.png`、`art-starry.jpg`、`星魂1.png`、`星魂4.png`、
   `logo-official.png` 放进 `assets/cyrene/原图/`
2. 跑 `python tools/prepare_assets.py` 生成派生素材
3. 重启程序

没有素材时程序会自动退回「简约」主题，功能完全一样。
主题按钮在标题栏右侧，点它会循环切换。

---

## 画廊

标题栏有个「画廊」按钮，从指定目录读图并排成网格。

默认读程序旁的 `Cyrene\` 文件夹。如果图片放在别处，
去「设置 → 画廊目录」改路径，支持 jpg / png / webp / bmp。

没有图片时这一页会提示目录位置，不影响其他功能。

---

## 自己打包 exe

```bat
.venv\Scripts\python.exe tools\prepare_assets.py
.venv\Scripts\python.exe -m PyInstaller build_exe.spec --noconfirm --clean
```

产物在 `dist\Ripple\`，整个文件夹拷走就能用，约 130 MB（不含画廊素材）。

`build_exe.spec` 里有个 `GALLERY_INCLUDE` 开关，
设成 `False` 就不会把 `Cyrene\` 那 190 MB 打包进 exe。

---

## 目录结构

```
Routine/
├── Anigame-script-manager/     主程序
│   ├── core/core.py            执行器、配置、超时、日志
│   ├── external_watch.py       MaaEnd 用游戏进程判断完成
│   ├── ui/main_window_new.py   主界面
│   ├── ui/theme.py             主题 token
│   ├── ui/splash.py            启动画面
│   ├── ui/paths.py             路径解析（源码 / exe 通用）
│   ├── ui/task_settings.py     单个任务的设置面板
│   ├── ui/after_done.py        结束后操作面板
│   └── main.py                 入口
├── status/                     状态读取
│   ├── providers.py            米游社 / 森空岛各游戏数据
│   └── skland.py               森空岛签名与自动续期
├── tools/
│   ├── selfcheck.py            静态检查（变量未定义、裸 except 等）
│   ├── prepare_assets.py       从原图生成派生素材
│   ├── update_check.py         各工具版本检查
│   └── verify_background.py    用假任务验证并发逻辑
└── assets/cyrene/              美术素材（不入库，见上）
```

---

## 开发

### 自检

```bat
.venv\Scripts\python.exe tools\selfcheck.py
```

检查：变量在赋值前使用、重复定义、裸 `except`、硬编码敏感信息。
当前 36 个文件 0 错误。

### 验证并发逻辑

```bat
.venv\Scripts\python.exe tools\verify_background.py
```

用假任务跑一遍真实的调度器，不碰任何游戏。

### 界面预览

不需要显示器的环境下也能截图：

```bat
set QT_QPA_PLATFORM=offscreen
.venv\Scripts\python.exe tools\preview_ui.py
```

---

## 一些实现上的取舍

**为什么不用固定等待时长判断任务结束**
任务真实耗时从 40 秒到 4 小时 51 分都出现过（同一台机器、同一个工具）。
按时间判断必然误伤，所以改成：有进程盯进程、有日志盯日志、都没有才用超时兜底。

**为什么超时填 0 表示不限制**
因为「跑得久」和「卡死了」是两件事。前者不该被杀，后者需要兜底。
默认给一个宽松上限，真需要时也可以完全关掉。

**为什么 MAA 排在队列最后**
它是「启动后不等待」，排中间的话会和下一个任务同时跑。
MAA 用模拟器 ADB 通道，其他工具用 pyautogui 抢真实键鼠，两个一起跑会互相干扰。

**为什么打包用目录版不用单文件**
单文件每次启动都要把 130 MB 解包到临时目录，要等好几秒。
游戏日常是每天要开的东西，这几秒不值得省。

---

## 已知问题

- **打包成 exe 后未做完整的回归测试**（资源加载已验证，任务执行未测）
- `run_queue.py`（命令行版）没有实现「后台并行」和「启动后不等待」
- 森空岛接口偶发不稳定，可能返回「请求异常」，重新读取通常就好了
- 星铁的三月七小助手不会自己关游戏，需要在「结束后操作」里勾上关闭

---

## 许可

代码以 MIT 许可发布，见 [LICENSE](LICENSE)。

**仓库不包含任何游戏美术素材。** `assets/` 下的图片版权归米哈游（miHoYo / HoYoverse）所有，
不入库、不随本项目分发。这个项目与米哈游没有任何关联。

用自动化工具操作游戏可能违反游戏用户协议，请自行评估风险。
