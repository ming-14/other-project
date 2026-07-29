from PyQt5.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QPainter, QColor, QPen
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QWidget, QFrame, QSizePolicy
from qfluentwidgets import (
    SubtitleLabel, PushButton, SpinBox, TransparentToolButton,
    FluentIcon, BodyLabel, isDarkTheme, SimpleCardWidget,
)
from core.logger import get_logger

logger = get_logger("right_panel")

PANEL_EXPANDED_WIDTH = 280
COLLAPSED_BUTTON_WIDTH = 40

GREEN_BG = QColor(16, 124, 16)
GREEN_BG_HOVER = QColor(18, 138, 18)
GREEN_BORDER = QColor(14, 107, 14)


class PickButton(PushButton):
    _checked = False

    def setChecked(self, checked: bool):
        self._checked = checked
        self.update()

    def isChecked(self) -> bool:
        return self._checked

    def paintEvent(self, e):
        if self._checked:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            r = 5
            if self.isPressed:
                bg, border = GREEN_BORDER, GREEN_BORDER
            elif self.isHover:
                bg, border = GREEN_BG_HOVER, GREEN_BORDER
            else:
                bg, border = GREEN_BG, GREEN_BORDER
            painter.setPen(QPen(border, 1))
            painter.setBrush(bg)
            painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), r, r)
            painter.setPen(QColor(255, 255, 255))
            painter.setFont(self.font())
            painter.drawText(self.rect(), Qt.AlignCenter, self.text())
            painter.end()
        else:
            super().paintEvent(e)


class RightPanel(QFrame):
    pickCountChanged = pyqtSignal(int)
    collapseChanged = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_collapsed = False
        self._current_count = 1
        self._setup_ui()
        self._setup_animation()

    def _setup_ui(self):
        self.setObjectName("rightPanel")

        self.mainLayout = QHBoxLayout(self)
        self.mainLayout.setContentsMargins(0, 0, 0, 0)
        self.mainLayout.setSpacing(0)

        self.contentWidget = SimpleCardWidget(self)
        self.contentWidget.setFixedWidth(PANEL_EXPANDED_WIDTH)
        self.contentLayout = QVBoxLayout(self.contentWidget)
        self.contentLayout.setContentsMargins(12, 16, 12, 16)
        self.contentLayout.setSpacing(10)

        headerRow = QHBoxLayout()
        headerRow.setSpacing(0)
        self.titleLabel = SubtitleLabel("抽取人数", self.contentWidget)
        headerRow.addWidget(self.titleLabel)
        headerRow.addStretch(1)

        self.collapseBtn = TransparentToolButton(FluentIcon.PAGE_RIGHT, self.contentWidget)
        self.collapseBtn.setFixedSize(28, 28)
        self.collapseBtn.clicked.connect(self.toggle_collapse)
        headerRow.addWidget(self.collapseBtn)

        self.contentLayout.addLayout(headerRow)

        self.btnRow = QHBoxLayout()
        self.btnRow.setSpacing(4)
        self.btnRow.setContentsMargins(0, 0, 0, 0)

        self._preset_buttons: list[PickButton] = []
        for i in range(1, 6):
            btn = PickButton(str(i), self.contentWidget)
            btn.setChecked(i == 1)
            btn.setFixedSize(42, 42)
            btn.clicked.connect(lambda checked, val=i: self._on_preset_clicked(val))
            self._preset_buttons.append(btn)
            self.btnRow.addWidget(btn)

        self.contentLayout.addLayout(self.btnRow)

        self.customRow = QHBoxLayout()
        self.customRow.setSpacing(6)
        self.customLabel = BodyLabel("自定义", self.contentWidget)
        self.spinBox = SpinBox(self.contentWidget)
        self.spinBox.setRange(1, 99)
        self.spinBox.setValue(1)
        self.spinBox.setFixedWidth(120)
        self.spinBox.valueChanged.connect(self._on_spinbox_changed)
        self.spinBox.lineEdit().editingFinished.connect(lambda: self.spinBox.clearFocus())
        self.customRow.addWidget(self.customLabel)
        self.customRow.addWidget(self.spinBox)
        self.contentLayout.addLayout(self.customRow)

        self.contentLayout.addStretch(1)

        self.expandBtn = TransparentToolButton(FluentIcon.PAGE_LEFT, self)
        self.expandBtn.setFixedSize(COLLAPSED_BUTTON_WIDTH, COLLAPSED_BUTTON_WIDTH)
        self.expandBtn.clicked.connect(self.toggle_collapse)
        self.expandBtn.setCursor(Qt.PointingHandCursor)
        self.expandBtn.setVisible(False)

        self.mainLayout.addWidget(self.contentWidget, 0, Qt.AlignRight)
        self.mainLayout.addWidget(self.expandBtn, 0, Qt.AlignTop | Qt.AlignRight)

        self.setFixedWidth(PANEL_EXPANDED_WIDTH)

    def _setup_animation(self):
        self._anim_min = QPropertyAnimation(self.contentWidget, b"minimumWidth")
        self._anim_min.setDuration(250)
        self._anim_min.setEasingCurve(QEasingCurve.OutCubic)
        self._anim_min.valueChanged.connect(self._sync_panel_width)
        self._anim_min.finished.connect(self._on_anim_finished)

        self._anim_max = QPropertyAnimation(self.contentWidget, b"maximumWidth")
        self._anim_max.setDuration(250)
        self._anim_max.setEasingCurve(QEasingCurve.OutCubic)

    def _on_preset_clicked(self, value: int):
        self._current_count = value
        for i, btn in enumerate(self._preset_buttons):
            btn.setChecked(i + 1 == value)
        self.spinBox.setValue(value)
        self.pickCountChanged.emit(value)
        logger.info("预设抽取人数: %d", value)

    def _on_spinbox_changed(self, value: int):
        self._current_count = value
        for i, btn in enumerate(self._preset_buttons):
            btn.setChecked(i + 1 == value)
        self.pickCountChanged.emit(value)
        logger.info("自定义抽取人数: %d", value)

    def toggle_collapse(self):
        self._is_collapsed = not self._is_collapsed
        if self._is_collapsed:
            self._collapse()
        else:
            self._expand()
        self.collapseChanged.emit(self._is_collapsed)

    def _collapse(self):
        self._anim_min.stop()
        self._anim_max.stop()
        self._anim_min.setStartValue(self.contentWidget.width())
        self._anim_min.setEndValue(0)
        self._anim_max.setStartValue(self.contentWidget.width())
        self._anim_max.setEndValue(0)
        self._anim_min.start()
        self._anim_max.start()
        logger.info("右栏收缩中")

    def _on_collapse_finished(self):
        self.contentWidget.setVisible(False)
        self.expandBtn.setVisible(True)
        self.setFixedWidth(COLLAPSED_BUTTON_WIDTH)
        logger.info("右栏已收缩")

    def _expand(self):
        self.expandBtn.setVisible(False)
        self.contentWidget.setVisible(True)
        self.contentWidget.setFixedWidth(0)
        self.setFixedWidth(0)
        self._anim_min.stop()
        self._anim_max.stop()
        self._anim_min.setStartValue(0)
        self._anim_min.setEndValue(PANEL_EXPANDED_WIDTH)
        self._anim_max.setStartValue(0)
        self._anim_max.setEndValue(PANEL_EXPANDED_WIDTH)
        self._anim_min.start()
        self._anim_max.start()
        self.collapseBtn.setIcon(FluentIcon.PAGE_RIGHT)
        logger.info("右栏已展开")

    def _sync_panel_width(self, value):
        self.setFixedWidth(int(value))

    def _on_anim_finished(self):
        if self._is_collapsed:
            self.contentWidget.setVisible(False)
            self.expandBtn.setVisible(True)
            self.setFixedWidth(COLLAPSED_BUTTON_WIDTH)
        else:
            self.setFixedWidth(PANEL_EXPANDED_WIDTH)

    @property
    def is_collapsed(self) -> bool:
        return self._is_collapsed

    def set_pick_count(self, count: int):
        self._current_count = count
        self.spinBox.setValue(count)
        for i, btn in enumerate(self._preset_buttons):
            btn.setChecked(i + 1 == count)

    def mousePressEvent(self, e):
        self.spinBox.clearFocus()
        super().mousePressEvent(e)
