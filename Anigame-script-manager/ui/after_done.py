# -*- coding: utf-8 -*-
"""队列结束后的操作设置面板。

参考 MAA 的「完成后」选项组：退出模拟器 / 退出工具 / 锁屏 / 睡眠 /
休眠 / 关机，彼此独立勾选，而非单一的「结束后关机」开关。

拆开的原因：这几项影响程度差异很大。仅需挂机者可选择锁屏，
夜间执行后为节省电力可选择睡眠，而关机是影响最大的一项。
合并为单一开关，等于只提供「不操作」与「直接关机」两种选择。
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core import AppConfig
from ui import theme as theme_mod


class AfterDoneDialog(QDialog):
    """队列结束后的操作设置。

    参考 MAA 的「完成后」选项组：退出模拟器 / 退出工具 / 锁屏 / 睡眠 /
    休眠 / 关机，彼此独立勾选，而非单一的「结束后关机」开关。

    拆开的原因：这几项影响程度差异很大。仅需挂机者可选择锁屏，
    夜间执行后为节省电力可选择睡眠，而关机是影响最大的一项。
    合并为单一开关，等于只提供「不操作」与「直接关机」两种选择。
    """

    def __init__(self, config: AppConfig, theme: theme_mod.Theme, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("结束后操作")
        self.setMinimumWidth(460)
        self._config = config
        self._theme = theme

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 14)
        root.setSpacing(10)

        title = QLabel("队列结束后")
        title.setObjectName("SectionTitle")
        root.addWidget(title)

        hint = QLabel("以下操作在最后一个任务结束后依次执行，可多选。")
        hint.setObjectName("SectionHint")
        hint.setWordWrap(True)
        root.addWidget(hint)

        # ---- 清理项：优先执行 ----
        root.addWidget(self._group("清理"))

        self.close_game_cb = QCheckBox("关闭游戏本体")
        self.close_game_cb.setChecked(config.after_done_close_game)
        self.close_game_cb.setToolTip(
            "各工具通常会在跑完后自己关游戏。\n"
            "勾这项是兜底：万一游戏还开着，队列结束时替你关掉，\n"
            "免得自动关机卡在「有程序阻止关机」。"
        )
        root.addWidget(self.close_game_cb)

        self.close_emulator_cb = QCheckBox("退出模拟器（MuMu）")
        self.close_emulator_cb.setChecked(config.after_done_close_emulator)
        root.addWidget(self.close_emulator_cb)

        self.close_tools_cb = QCheckBox("关闭本次启动的工具进程")
        self.close_tools_cb.setToolTip("BetterGI / MAA / 一条龙 / MaaEnd 等")
        self.close_tools_cb.setChecked(config.after_done_close_tools)
        root.addWidget(self.close_tools_cb)

        # ---- 电源类：后执行 ----
        root.addWidget(self._group("电源"))

        self.lock_cb = QCheckBox("锁屏")
        self.lock_cb.setChecked(config.after_done_lock)
        root.addWidget(self.lock_cb)

        self.sleep_cb = QCheckBox("睡眠")
        self.sleep_cb.setChecked(config.after_done_sleep)
        root.addWidget(self.sleep_cb)

        self.hibernate_cb = QCheckBox("休眠（需要在系统里启用休眠功能）")
        self.hibernate_cb.setChecked(config.after_done_hibernate)
        root.addWidget(self.hibernate_cb)

        self.shutdown_cb = QCheckBox("关机")
        self.shutdown_cb.setToolTip("关机命令会立即发出，System 在下方设定的延迟后执行；期间可取消。")
        self.shutdown_cb.setChecked(config.shutdown_after_done)
        root.addWidget(self.shutdown_cb)

        delay_row = QVBoxLayout()
        delay_row.setContentsMargins(22, 0, 0, 0)
        self.delay_spin = QSpinBox()
        self.delay_spin.setRange(0, 3600)
        self.delay_spin.setSingleStep(30)
        self.delay_spin.setSuffix(" 秒")
        self.delay_spin.setValue(int(config.shutdown_delay_seconds))
        self.delay_spin.setEnabled(config.shutdown_after_done)
        delay_row.addWidget(QLabel("关机延迟（延迟期间可取消）"))
        delay_row.addWidget(self.delay_spin)
        root.addLayout(delay_row)

        # 睡眠和休眠互斥：两个都勾没有意义，勾一个就把另一个放开。
        self.sleep_cb.toggled.connect(self._sync_power)
        self.hibernate_cb.toggled.connect(self._sync_power)
        self.shutdown_cb.toggled.connect(self.delay_spin.setEnabled)

        root.addStretch(1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("保存")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _group(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("SideHeading")
        return lbl

    def _sync_power(self, checked: bool) -> None:
        """睡眠 / 休眠只能选一个。"""
        if not checked:
            return
        sender = self.sender()
        other = self.hibernate_cb if sender is self.sleep_cb else self.sleep_cb
        if other.isChecked():
            other.blockSignals(True)
            other.setChecked(False)
            other.blockSignals(False)

    def apply_to(self, config: AppConfig) -> None:
        config.after_done_close_game = self.close_game_cb.isChecked()
        config.after_done_close_emulator = self.close_emulator_cb.isChecked()
        config.after_done_close_tools = self.close_tools_cb.isChecked()
        config.after_done_lock = self.lock_cb.isChecked()
        config.after_done_sleep = self.sleep_cb.isChecked()
        config.after_done_hibernate = self.hibernate_cb.isChecked()
        config.shutdown_after_done = self.shutdown_cb.isChecked()
        config.shutdown_delay_seconds = int(self.delay_spin.value())
