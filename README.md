# 涟漪 · Ripples

把每天重复的游戏日常自动化掉，点一次就开始，跑完就不用管了。

一个 Windows 桌面小工具：把若干现成的游戏自动化工具排成一条队列，按顺序启动、
等它们各自跑完、再处理下一个。原神、终末地、绝区零、崩铁、明日方舟。

> 「做这个是为了每日重复的无聊的日常不用自己做，然后轻松。」

---

## 它做的事

- **排队启动**：拖拽排序，一次点「开始执行」跑完整条队列
- **等待真实结束**：不是睡固定秒数，而是盯进程 / 盯日志判断任务真的完了
- **超时可调**：每个任务单独设最大运行时间，填 0 表示不限制
- **结束后操作**：关游戏、关工具、退模拟器、锁屏、睡眠、休眠、关机，可多选
- **今日状态**：从米游社 / 森空岛读各游戏的体力与日常进度，一屏看完
- **两个界面**：启动画面 + 主界面，支持深浅几套主题

## 它不做的事

- **不代替你设置各游戏工具**。副本打哪个、体力怎么花，都在各自工具里配。
  这里只管「什么时候启动、什么时候算结束」。
- **不修改游戏**，不注入、不读内存。全靠调用现成的开源工具。
- **不做「清没清」的判断**，只把数据摊出来让你自己看。

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

### 1. 准备 Python 环境

需要 Python 3.10 或更高版本。

```bat
git clone <你的仓库地址>
cd Routine
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 2. 配置各工具的路径

首次启动时队列是空的。点每个任务右侧的「设置」，把程序路径填成你自己机器上的位置。
任务列表存在 `Anigame-script-manager/config.json`，也可以直接编辑。

### 3. 启动

```bat
双击 打开界面.bat
```

或者：

```bat
.venv\Scripts\python.exe Anigame-script-manager\main.py
```

**需要管理员权限**：BetterGI 这类工具要模拟键鼠操作，没有管理员权限会失败。

### 4. 关于主题和素材

程序默认带一个「简约」主题，**不需要任何图片素材**，开箱即用。

界面里还有几套昔涟主题，但它们依赖《崩坏：星穹铁道》的官方美术图。
这些图**不随仓库分发**（版权属于米哈游），想用的话自己准备：

1. 把 `art-reading.png`、`art-starry.jpg`、`星魂1.png`、`星魂4.png`、
   `logo-official.png` 放进 `assets/cyrene/原图/`
2. 跑 `python tools/prepare_assets.py` 生成派生素材
3. 重启程序

没有素材时程序会自动退回「简约」主题，功能完全一样。

### 5. 打包成 exe（可选）

```bat
.venv\Scripts\python.exe tools\prepare_assets.py
.venv\Scripts\python.exe -m PyInstaller build_exe.spec --noconfirm --clean
```

产物在 `dist\涟漪\`，整个文件夹拷走就能用。

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
