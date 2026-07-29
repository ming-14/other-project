from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QWidget, QLineEdit
from qfluentwidgets import (
    ScrollArea, SettingCardGroup, ExpandSettingCard,
    RangeSettingCard, OptionsSettingCard, FluentIcon, BodyLabel,
    PrimaryPushButton, PushButton, ListWidget, SettingCard,
    isDarkTheme, InfoBar, InfoBarPosition,
)
from qfluentwidgets.common.config import (
    ConfigItem, RangeConfigItem, RangeValidator,
    OptionsConfigItem, OptionsValidator,
)
from core.logger import get_logger

logger = get_logger("settings_page")


class NameListCard(ExpandSettingCard):
    """名单管理卡片"""

    namesChanged = None  # will be set as signal

    def __init__(self, names: list, parent=None):
        super().__init__(FluentIcon.PEOPLE, "名单管理", "添加或删除点名名单中的人员", parent)
        self._names = list(names)
        self._setup_content()

    def _setup_content(self):
        self.listWidget = ListWidget(self.view)
        self.listWidget.setFixedHeight(200)
        for name in self._names:
            self.listWidget.addItem(name)

        self.inputLayout = QHBoxLayout()
        self.inputLineEdit = QLineEdit(self.view)
        self.inputLineEdit.setPlaceholderText("输入姓名")
        self.inputLineEdit.setFixedHeight(32)

        self.addButton = PrimaryPushButton("添加", self.view)
        self.addButton.setFixedHeight(32)
        self.addButton.setFixedWidth(80)
        self.addButton.clicked.connect(self._on_add)

        self.deleteButton = PushButton("删除选中", self.view)
        self.deleteButton.setFixedHeight(32)
        self.deleteButton.setFixedWidth(90)
        self.deleteButton.clicked.connect(self._on_delete)

        self.inputLayout.addWidget(self.inputLineEdit)
        self.inputLayout.addWidget(self.addButton)
        self.inputLayout.addWidget(self.deleteButton)

        self.viewLayout.addWidget(self.listWidget)
        self.viewLayout.addLayout(self.inputLayout)

    def _on_add(self):
        name = self.inputLineEdit.text().strip()
        if not name:
            return
        self._names.append(name)
        self.listWidget.addItem(name)
        self.inputLineEdit.clear()
        logger.info("添加名字: %s", name)

    def _on_delete(self):
        current = self.listWidget.currentRow()
        if current < 0:
            return
        removed = self._names.pop(current)
        self.listWidget.takeItem(current)
        logger.info("删除名字: %s", removed)

    def get_names(self) -> list:
        return list(self._names)

    def update_names(self, names: list):
        self._names = list(names)
        self.listWidget.clear()
        for name in self._names:
            self.listWidget.addItem(name)


class SettingsPage(ScrollArea):
    """设置页面"""

    namesChanged = None  # will use callback
    themeChanged = None
    animationIntervalChanged = None

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self._config = config
        self.setObjectName("settingsPage")
        self.setWidgetResizable(True)
        self.setFrameShape(self.NoFrame)

        self.scrollWidget = QWidget(self)
        self.scrollWidget.setObjectName("settingsScrollWidget")
        self.vBoxLayout = QVBoxLayout(self.scrollWidget)
        self.vBoxLayout.setContentsMargins(36, 20, 36, 20)
        self.vBoxLayout.setSpacing(28)

        self._setup_ui()
        self.setWidget(self.scrollWidget)
        self._apply_theme_bg()

        self._names_changed_callback = None
        self._theme_changed_callback = None
        self._interval_changed_callback = None

    def _setup_ui(self):
        # 名单管理组
        self.nameGroup = SettingCardGroup("名单", self.scrollWidget)
        self.nameListCard = NameListCard(self._config.names, self.nameGroup)
        self.nameListCard.addButton.clicked.connect(self._on_names_changed)
        self.nameListCard.deleteButton.clicked.connect(self._on_names_changed)
        self.nameGroup.addSettingCard(self.nameListCard)

        # 显示组
        self.displayGroup = SettingCardGroup("显示", self.scrollWidget)

        self.intervalCard = RangeSettingCard(
            RangeConfigItem("animation_interval", "", 60, RangeValidator(20, 300)),
            FluentIcon.SPEED_HIGH,
            "闪动速度",
            "调整名字闪动的间隔（越小越快）",
            self.displayGroup,
        )
        self.intervalCard.slider.setRange(20, 300)
        self.intervalCard.slider.setValue(self._config.animation_interval)
        self.intervalCard.valueChanged.connect(self._on_interval_changed)
        self.displayGroup.addSettingCard(self.intervalCard)

        # 主题组
        self.themeGroup = SettingCardGroup("主题", self.scrollWidget)
        self.themeCard = OptionsSettingCard(
            OptionsConfigItem("theme", "", "auto", OptionsValidator(["auto", "light", "dark"])),
            FluentIcon.PALETTE,
            "主题模式",
            "切换应用主题",
            ["跟随系统", "亮色", "暗色"],
            self.themeGroup,
        )
        self.themeCard.setValue(self._config.theme)
        self.themeCard.optionChanged.connect(self._on_theme_changed)
        self.themeGroup.addSettingCard(self.themeCard)

        self.vBoxLayout.addWidget(self.nameGroup)
        self.vBoxLayout.addWidget(self.displayGroup)
        self.vBoxLayout.addWidget(self.themeGroup)
        self.vBoxLayout.addStretch(1)

    def _on_names_changed(self):
        names = self.nameListCard.get_names()
        self._config.names = names
        if self._names_changed_callback:
            self._names_changed_callback(names)

    def _on_interval_changed(self, value):
        self._config.animation_interval = value
        if self._interval_changed_callback:
            self._interval_changed_callback(value)
        logger.info("闪动间隔已更改: %d ms", value)

    def _on_theme_changed(self, configItem):
        value = configItem.value
        self._config.theme = value
        self._apply_theme_bg()
        if self._theme_changed_callback:
            self._theme_changed_callback(value)
        logger.info("主题已更改: %s", value)

    def set_callbacks(self, names_changed=None, theme_changed=None, interval_changed=None):
        self._names_changed_callback = names_changed
        self._theme_changed_callback = theme_changed
        self._interval_changed_callback = interval_changed

    def update_names_display(self, names: list):
        """外部更新名单显示"""
        self.nameListCard.update_names(names)

    def _apply_theme_bg(self):
        """根据当前主题设置背景色"""
        bg = "#1e1e1e" if isDarkTheme() else "#f5f5f5"
        self.setStyleSheet(f"""
            QScrollArea {{ border: none; background: {bg}; }}
            QWidget#settingsScrollWidget {{ background: {bg}; }}
        """)

    def showEvent(self, e):
        super().showEvent(e)
        self._apply_theme_bg()
