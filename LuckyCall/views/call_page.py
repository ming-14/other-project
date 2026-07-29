from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QWidget, QSizePolicy
from qfluentwidgets import (
    DisplayLabel, TitleLabel, BodyLabel, PrimaryPushButton, PushButton,
    FluentIcon, InfoBar, InfoBarPosition, isDarkTheme,
)
from core.name_manager import NameManager, CallMode, CallState
from core.logger import get_logger

logger = get_logger("call_page")

DEFAULT_SCALE = 1.0
MIN_SCALE = 0.3
MAX_SCALE = 3.0
SCALE_STEP = 0.1


class CallPage(QWidget):
    """点名页面（随机/去重共用）"""

    def __init__(self, mode: CallMode, name_manager: NameManager, parent=None):
        super().__init__(parent)
        self._mode = mode
        self._manager = name_manager
        self._manager.mode = mode
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_roll_tick)
        self._scale = DEFAULT_SCALE
        self._animation_interval = 60  # 默认闪动间隔

        self.setObjectName(f"callPage_{mode.value}")
        self._setup_ui()
        self._update_display_idle()

    def _setup_ui(self):
        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setContentsMargins(40, 40, 40, 30)
        self.vBoxLayout.setSpacing(20)

        self.nameContainer = QWidget(self)
        self.nameContainer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.nameContainerLayout = QVBoxLayout(self.nameContainer)
        self.nameContainerLayout.setContentsMargins(0, 0, 0, 0)
        self.nameContainerLayout.setAlignment(Qt.AlignCenter)

        self.nameLabel = DisplayLabel("准备点名", self)
        self.nameLabel.setAlignment(Qt.AlignCenter)
        self.nameLabel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.nameContainerLayout.addWidget(self.nameLabel)

        self.remainLabel = BodyLabel("", self)
        self.remainLabel.setAlignment(Qt.AlignCenter)
        self.remainLabel.setVisible(self._mode == CallMode.DEDUP)

        self.buttonLayout = QHBoxLayout()
        self.buttonLayout.setSpacing(16)
        self.buttonLayout.setAlignment(Qt.AlignCenter)

        self.startButton = PrimaryPushButton("开始点名", self)
        self.startButton.setIcon(FluentIcon.PLAY)
        self.startButton.setFixedHeight(44)
        self.startButton.setFixedWidth(180)
        self.startButton.clicked.connect(self._on_start_clicked)

        self.resetButton = PushButton("重置", self)
        self.resetButton.setIcon(FluentIcon.SYNC)
        self.resetButton.setFixedHeight(44)
        self.resetButton.setFixedWidth(120)
        self.resetButton.clicked.connect(self._on_reset_clicked)
        self.resetButton.setVisible(False)

        self.exitButton = PushButton("退出", self)
        self.exitButton.setIcon(FluentIcon.CLOSE)
        self.exitButton.setFixedHeight(44)
        self.exitButton.setFixedWidth(120)
        self.exitButton.clicked.connect(self._on_exit_clicked)

        self.buttonLayout.addWidget(self.startButton)
        self.buttonLayout.addWidget(self.resetButton)
        self.buttonLayout.addWidget(self.exitButton)

        self.vBoxLayout.addWidget(self.nameContainer, stretch=1)
        self.vBoxLayout.addWidget(self.remainLabel, alignment=Qt.AlignCenter)
        self.vBoxLayout.addLayout(self.buttonLayout)

    def _update_display_idle(self):
        if self._mode == CallMode.DEDUP:
            self.remainLabel.setVisible(True)
            self.remainLabel.setText(f"剩余: {self._manager.remaining_count} 人")
        self.nameLabel.setText("准备点名")
        self._adjust_font_size("准备点名")

    def _adjust_font_size(self, text: str):
        """根据名字长度、窗口大小和缩放比例动态调整字号"""
        container_w = max(self.nameContainer.width() - 40, 200)
        container_h = max(self.nameContainer.height() - 40, 100)

        char_count = len(text)
        if char_count == 0:
            return

        base_size = min(container_w / (char_count * 1.2), container_h * 0.6)
        base_size = max(base_size, 24)

        scaled_size = base_size * self._scale

        # 确保不溢出屏幕：字号不能超过容器宽/高
        max_by_width = container_w / max(char_count * 0.6, 1)
        max_by_height = container_h * 0.9
        scaled_size = min(scaled_size, max_by_width, max_by_height)
        scaled_size = max(scaled_size, 12)

        font = self.nameLabel.font()
        font.setPixelSize(int(scaled_size))
        self.nameLabel.setFont(font)

    def _on_start_clicked(self):
        if self._manager.state == CallState.ROLLING:
            self._stop_rolling()
        else:
            self._start_rolling()

    def _start_rolling(self):
        if self._manager.is_exhausted():
            InfoBar.warning(
                "提示", "所有人已点名完毕，请点击重置",
                parent=self, duration=3000, position=InfoBarPosition.TOP,
            )
            return

        if self._manager.is_insufficient():
            InfoBar.warning(
                "提示", f"剩余人数不足，当前仅剩 {self._manager.remaining_count} 人",
                parent=self, duration=3000, position=InfoBarPosition.TOP,
            )
            return

        self._manager.start()
        self._timer.start(self._animation_interval)

        self.startButton.setText("停止点名")
        self.startButton.setIcon(FluentIcon.PAUSE)
        self.resetButton.setVisible(False)
        logger.info("开始闪动，模式: %s，间隔: %d ms", self._mode.value, self._animation_interval)

    def _stop_rolling(self):
        self._timer.stop()
        results = self._manager.stop()

        if results:
            display_text = "、".join(results)
            self.nameLabel.setText(display_text)
            self._adjust_font_size(display_text)
        else:
            self.nameLabel.setText("无结果")
            self._adjust_font_size("无结果")

        self.startButton.setText("开始点名")
        self.startButton.setIcon(FluentIcon.PLAY)

        if self._mode == CallMode.DEDUP:
            self.remainLabel.setText(f"剩余: {self._manager.remaining_count} 人")
            self.resetButton.setVisible(True)

            if self._manager.is_exhausted():
                InfoBar.warning(
                    "提示", "所有人已点名完毕，请点击重置",
                    parent=self, duration=5000, position=InfoBarPosition.TOP,
                )
                logger.info("去重点名：所有人已点名完毕")

    def _on_roll_tick(self):
        name = self._manager.roll()
        if name:
            self.nameLabel.setText(name)
            self._adjust_font_size(name)

    def _on_reset_clicked(self):
        self._manager.reset()
        self._update_display_idle()
        self.resetButton.setVisible(False)
        InfoBar.success(
            "提示", "候选池已重置",
            parent=self, duration=2000, position=InfoBarPosition.TOP,
        )
        logger.info("候选池已重置")

    def _on_exit_clicked(self):
        from PyQt5.QtWidgets import QApplication
        logger.info("用户点击退出按钮")
        QApplication.quit()

    def set_animation_interval(self, interval: int):
        """设置闪动间隔，保存并立即应用到定时器"""
        self._animation_interval = interval
        if self._timer.isActive():
            self._timer.setInterval(interval)
        logger.info("闪动间隔已设置为: %d ms", interval)

    def update_names(self, names: list):
        self._manager.update_names(names)
        if self._manager.state != CallState.ROLLING:
            self._update_display_idle()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        current_text = self.nameLabel.text()
        if current_text:
            self._adjust_font_size(current_text)

    def wheelEvent(self, e):
        """Ctrl+滚轮调整名字显示比例"""
        if e.modifiers() & Qt.ControlModifier:
            delta = e.angleDelta().y()
            if delta > 0:
                self._scale = min(self._scale + SCALE_STEP, MAX_SCALE)
            elif delta < 0:
                self._scale = max(self._scale - SCALE_STEP, MIN_SCALE)
            current_text = self.nameLabel.text()
            if current_text:
                self._adjust_font_size(current_text)
            logger.info("名字显示比例调整: %.1f", self._scale)
            e.accept()
        else:
            super().wheelEvent(e)
