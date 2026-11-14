# -*- coding: utf-8 -*-
"""应用设置面板。

和「任务设置」分开：那个管单个任务（路径、参数、超时），
这个管整个程序（画廊目录、超时截图这类全局项）。

为什么不塞进任务设置：任务设置是从某一行的「设置」点进去的，
天然带上「这个任务」的语境；把全局项混进去，用户会以为改的是局部。
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core import AppConfig
from ui import theme as theme_mod


class AppSettingsDialog(QDialog):
    """程序级设置。"""

    def __init__(self, config: AppConfig, theme: theme_mod.Theme, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("应用设置")
        self.setMinimumWidth(560)
        self._config = config

        self.setStyleSheet(theme_mod.stylesheet(theme))

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 14)
        root.setSpacing(12)

        title = QLabel("应用设置")
        title.setObjectName("SectionTitle")
        root.addWidget(title)

        # ---------------- 画廊 ----------------
        root.addWidget(self._group("画廊"))

        hint = QLabel(
            "「画廊」按钮点开时从这个目录读图。留空则用程序旁的 Cyrene 文件夹。"
        )
        hint.setObjectName("SectionHint")
        hint.setWordWrap(True)
        root.addWidget(hint)

        dir_row = QHBoxLayout()
        dir_row.setSpacing(6)
        self.gallery_edit = QLineEdit(config.gallery_dir)
        self.gallery_edit.setPlaceholderText("留空 = 程序旁的 Cyrene 文件夹")
        dir_row.addWidget(self.gallery_edit, 1)

        browse = QPushButton("浏览…")
        browse.setObjectName("Ghost")
        browse.clicked.connect(self._browse_gallery)
        dir_row.addWidget(browse)

        clear = QPushButton("恢复默认")
        clear.setObjectName("Ghost")
        clear.clicked.connect(lambda: self.gallery_edit.setText(""))
        dir_row.addWidget(clear)

        dir_wrap = QWidget()
        dir_wrap.setLayout(dir_row)
        root.addWidget(dir_wrap)

        # 实时显示这个路径下有多少张图，省得填完才发现是空的
        self.gallery_info = QLabel("")
        self.gallery_info.setObjectName("SectionHint")
        root.addWidget(self.gallery_info)
        self.gallery_edit.textChanged.connect(self._update_gallery_info)
        self._update_gallery_info()

        # ---------------- 其他 ----------------
        root.addWidget(self._group("其他"))

        self.screenshot_cb = QCheckBox("超时处理时保存现场截图")
        self.screenshot_cb.setChecked(config.enable_timeout_screenshot)
        self.screenshot_cb.setToolTip("任务超时或卡住时截一张屏，存到 logs/screenshots/")
        root.addWidget(self.screenshot_cb)

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
    def _group(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("SideHeading")
        return lbl

    def _browse_gallery(self) -> None:
        current = self.gallery_edit.text().strip()
        if current and Path(current).is_dir():
            start = current
        else:
            start = str(Path.home())
        path = QFileDialog.getExistingDirectory(self, "选择图片目录", start)
        if path:
            self.gallery_edit.setText(path)

    def _update_gallery_info(self) -> None:
        """实时统计目录里的图片数，填错路径时立刻能看出来。"""
        from ui.gallery import EXTS, gallery_dir

        custom = self.gallery_edit.text().strip()
        target = gallery_dir(custom)

        if not target.is_dir():
            self.gallery_info.setText(f"目录不存在：{target}")
            return

        try:
            count = sum(1 for p in target.iterdir() if p.is_file() and p.suffix.lower() in EXTS)
        except OSError as exc:
            self.gallery_info.setText(f"读不了这个目录：{exc}")
            return

        suffix = "（默认位置）" if not custom else ""
        self.gallery_info.setText(f"{target}{suffix} — {count} 张图")

    def apply_to(self, config: AppConfig) -> None:
        config.gallery_dir = self.gallery_edit.text().strip()
        config.enable_timeout_screenshot = self.screenshot_cb.isChecked()
