"""
应用设置面板。

设置项持久化在 settings_backup.json（与主窗口设置同一文件），
由 Controller 负责读取、应用与保存。
"""
import os

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit,
    QPushButton, QSpinBox, QDoubleSpinBox, QFileDialog, QDialogButtonBox
)


class SettingsDialog(QDialog):
    def __init__(self, parent=None, settings: dict = None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setMinimumWidth(460)
        settings = settings or {}

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(10)

        self.spin_concurrency = QSpinBox()
        self.spin_concurrency.setRange(1, 8)
        self.spin_concurrency.setValue(int(settings.get("scrape_concurrency", 3)))
        form.addRow("刮削并发数:", self.spin_concurrency)

        self.spin_rate = QDoubleSpinBox()
        self.spin_rate.setRange(0.2, 5.0)
        self.spin_rate.setSingleStep(0.1)
        self.spin_rate.setSuffix(" 秒")
        self.spin_rate.setValue(float(settings.get("rate_limit_interval", 1.0)))
        form.addRow("请求最小间隔:", self.spin_rate)

        hint = QLabel("并发数只影响流水线深度；出网频率由请求间隔全局限速，\n调低间隔过猛可能被平台封禁 IP。")
        hint.setStyleSheet("color: #748297; font-size: 11px;")
        form.addRow("", hint)

        player_row = QHBoxLayout()
        self.player_input = QLineEdit(settings.get("custom_player_path", ""))
        self.player_input.setPlaceholderText("留空使用系统默认播放器")
        btn_browse = QPushButton("浏览...")
        btn_browse.clicked.connect(self._browse_player)
        player_row.addWidget(self.player_input)
        player_row.addWidget(btn_browse)
        form.addRow("自定义播放器:", player_row)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse_player(self):
        start_dir = "/Applications" if os.path.isdir("/Applications") else ""
        path, _ = QFileDialog.getOpenFileName(self, "选择播放器程序", start_dir)
        if path:
            self.player_input.setText(path)

    def values(self) -> dict:
        return {
            "scrape_concurrency": self.spin_concurrency.value(),
            "rate_limit_interval": round(self.spin_rate.value(), 2),
            "custom_player_path": self.player_input.text().strip(),
        }
