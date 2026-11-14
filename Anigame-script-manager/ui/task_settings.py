# -*- coding: utf-8 -*-
"""任务启动设置对话框。

学的是 MAA 那种结构：左边一列勾选项，右边是每个选项对应的参数，
点齿轮进去改，改完关掉就生效。任务行本身只留「名字 + 状态 + 时长」，
细节全部收进这里。

为什么这么做
------------
之前所有字段都挤在任务行上，一屏五行已经很满，再加东西就挤不动了。
但字段本身是有用的（路径、参数、等待模式、超时动作…），
只是不该一直摊在眼前。收进齿轮后面，要用的时候点开就行。
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

import core as core_mod
from core import TaskConfig
from ui import theme as theme_mod


class TaskSettingsDialog(QDialog):
    """单个任务的启动设置。"""

    def __init__(
        self,
        task: TaskConfig,
        theme: theme_mod.Theme,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle(f"任务设置 · {task.name}")
        self.setMinimumWidth(560)
        self._task = task
        self._theme = theme

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 14)
        root.setSpacing(12)

        head = QLabel(task.name)
        head.setObjectName("SectionTitle")
        root.addWidget(head)

        # ---------------- 启动 ----------------
        launch_box = QVBoxLayout()
        launch_box.setSpacing(6)
        launch_box.addWidget(self._group_title("启动"))

        form = QFormLayout()
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # 脚本路径 + 浏览
        path_row = QHBoxLayout()
        path_row.setSpacing(6)
        self.path_edit = QLineEdit(task.script_path)
        self.path_edit.setPlaceholderText(r"例如 A:\BetterGI\BetterGI.exe")
        path_row.addWidget(self.path_edit, 1)
        browse = QPushButton("浏览…")
        browse.setObjectName("Ghost")
        browse.clicked.connect(self._browse)
        path_row.addWidget(browse)
        path_wrap = QWidget()
        path_wrap.setLayout(path_row)
        form.addRow("程序", path_wrap)

        # 参数
        self.args_edit = QLineEdit(task.args)
        self.args_edit.setPlaceholderText("例如 startOneDragon，或 -o -c")
        form.addRow("启动参数", self.args_edit)

        self.use_args_cb = QCheckBox("启用上面的参数")
        self.use_args_cb.setChecked(task.use_args)
        form.addRow("", self.use_args_cb)

        # 等待方式
        self.wait_combo = QComboBox()
        for value, label in core_mod.WAIT_MODES.items():
            self.wait_combo.addItem(label, value)
        idx = self.wait_combo.findData(task.wait_mode)
        self.wait_combo.setCurrentIndex(max(0, idx))
        form.addRow("等待方式", self.wait_combo)
        launch_box.addLayout(form)
        root.addLayout(launch_box)

        # ---------------- 耗时 ----------------
        time_box = QVBoxLayout()
        time_box.setSpacing(6)
        time_box.addWidget(self._group_title("时长"))

        time_form = QFormLayout()
        time_form.setSpacing(8)
        time_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(0, 1440)
        self.timeout_spin.setSingleStep(5)
        self.timeout_spin.setSuffix(" 分钟")
        self.timeout_spin.setSpecialValueText("不限时")
        self.timeout_spin.setValue(int(task.timeout_minutes))
        time_form.addRow("最大运行时间", self.timeout_spin)

        self.action_combo = QComboBox()
        for value, label in core_mod.TIMEOUT_ACTIONS.items():
            self.action_combo.addItem(label, value)
        idx = self.action_combo.findData(task.timeout_action)
        self.action_combo.setCurrentIndex(max(0, idx))
        time_form.addRow("到时间后", self.action_combo)
        time_box.addLayout(time_form)
        root.addLayout(time_box)

        # ---------------- 排程 ----------------
        sched_box = QVBoxLayout()
        sched_box.setSpacing(6)
        sched_box.addWidget(self._group_title("排程"))

        # 「后台并行」只对走 ADB / 不抢真实键鼠的工具开放。
        #
        # 之前这里对每个任务都显示，是个错误：后台并行会让该任务启动后
        # 队列立刻继续，于是它和下一个任务会同时跑。像 BetterGI 和
        # 绝区零一条龙都用 pyautogui 操作前台窗口，两个一起跑会互相抢
        # 鼠标键盘，行为不可预期。
        # 目前只有 MAA 走模拟器 ADB 通道，所以只给它开这个选项。
        if self._supports_background(task):
            self.bg_cb = QCheckBox("后台并行：启动后队列继续，不等待其结束")
            self.bg_cb.setChecked(task.run_in_background)
            self.bg_cb.setToolTip("适用于通过模拟器 ADB 通道操作、不占用真实键鼠的工具（如 MAA）")
            sched_box.addWidget(self.bg_cb)
        else:
            self.bg_cb = None
            note = QLabel("该工具会操作前台窗口，不适用于后台并行")
            note.setObjectName("SectionHint")
            sched_box.addWidget(note)

        self.enabled_cb = QCheckBox("启用此任务")
        self.enabled_cb.setChecked(task.enabled)
        sched_box.addWidget(self.enabled_cb)
        root.addLayout(sched_box)

        root.addStretch(1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("保存")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    @staticmethod
    def _group_title(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("SideHeading")
        return lbl

    @staticmethod
    def _supports_background(task: TaskConfig) -> bool:
        """这个任务能不能用「后台并行」。

        判据是 exe 名：目前只有 MAA 走模拟器 ADB 通道，不碰真实键鼠。
        其余工具（BetterGI、一条龙、MaaEnd）都用 pyautogui 操作前台窗口，
        两个同时跑会互相抢输入。新增工具时如果确认它不抢前台，再加进来。
        """
        name = Path(task.script_path).name.lower()
        return name in {"maa.exe"}

    def _browse(self) -> None:
        # 起始目录：已经填了路径就用它的上级目录；没填就从用户主目录起。
        # 不写死盘符——那只是某台机器上的习惯，换台电脑可能没有那个盘。
        current = self.path_edit.text().strip()
        if current:
            start = str(Path(current).parent)
        else:
            start = str(Path.home())
        path, _ = QFileDialog.getOpenFileName(
            self, "选择程序", start, "程序 (*.exe *.bat *.cmd *.py);;所有文件 (*.*)"
        )
        if path:
            self.path_edit.setText(path)

    def apply_to(self, task: TaskConfig) -> None:
        """把界面上的值写回任务对象。"""
        task.script_path = self.path_edit.text().strip()
        task.args = self.args_edit.text().strip()
        task.use_args = self.use_args_cb.isChecked()
        task.wait_mode = self.wait_combo.currentData()
        task.timeout_minutes = int(self.timeout_spin.value())
        task.timeout_action = self.action_combo.currentData()
        # 只有真的显示了那个勾选框才写回，否则保持原值不动
        if self.bg_cb is not None:
            task.run_in_background = self.bg_cb.isChecked()
        task.enabled = self.enabled_cb.isChecked()
