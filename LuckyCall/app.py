from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QHBoxLayout
from qfluentwidgets import (
    FluentWindow, FluentIcon, NavigationItemPosition,
    setTheme, Theme, isDarkTheme,
)
from core.config import Config
from core.name_manager import NameManager, CallMode
from core.logger import get_logger
from views.call_page import CallPage
from views.settings_page import SettingsPage
from views.right_panel import RightPanel

logger = get_logger("app")


class LuckyCallWindow(FluentWindow):
    """LuckyCall 主窗口"""

    def __init__(self):
        super().__init__()
        self._config = Config()
        self._init_managers()
        self._init_ui()
        self._connect_signals()
        self._apply_theme()
        logger.info("LuckyCall 主窗口初始化完成")

    def _init_managers(self):
        """初始化数据管理器"""
        self._name_manager_random = NameManager(
            self._config.names, CallMode.RANDOM, self._config.pick_count
        )
        self._name_manager_dedup = NameManager(
            self._config.names, CallMode.DEDUP, self._config.pick_count
        )

    def _init_ui(self):
        """初始化 UI"""
        self.setWindowTitle("LuckyCall 点名")
        self.setMinimumSize(900, 600)
        self.resize(1100, 700)

        # 创建页面
        self.randomPage = CallPage(CallMode.RANDOM, self._name_manager_random, self)
        self.dedupPage = CallPage(CallMode.DEDUP, self._name_manager_dedup, self)
        self.settingsPage = SettingsPage(self._config, self)

        # 初始化闪动间隔
        self.randomPage.set_animation_interval(self._config.animation_interval)
        self.dedupPage.set_animation_interval(self._config.animation_interval)

        # 添加导航项
        self.addSubInterface(
            self.randomPage, FluentIcon.PEOPLE, "随机点名",
            position=NavigationItemPosition.TOP,
        )
        self.addSubInterface(
            self.dedupPage, FluentIcon.FILTER, "去重点名",
            position=NavigationItemPosition.TOP,
        )
        self.addSubInterface(
            self.settingsPage, FluentIcon.SETTING, "设置",
            position=NavigationItemPosition.BOTTOM,
        )

        # 创建右栏
        self.rightPanel = RightPanel(self)
        self.rightPanel.set_pick_count(self._config.pick_count)

        # 将右栏加到 widgetLayout（与 stackedWidget 同级，自动避开标题栏的 48px top margin）
        self.widgetLayout.addWidget(self.rightPanel, 0, Qt.AlignRight)

        # 设置页面回调
        self.settingsPage.set_callbacks(
            names_changed=self._on_names_changed,
            theme_changed=self._on_theme_changed,
            interval_changed=self._on_interval_changed,
        )

    def _connect_signals(self):
        """连接信号"""
        self.rightPanel.pickCountChanged.connect(self._on_pick_count_changed)
        self.rightPanel.collapseChanged.connect(self._on_right_panel_collapse)
        self.navigationInterface.displayModeChanged.connect(self._on_nav_mode_changed)

    def _apply_theme(self):
        """应用主题"""
        theme = self._config.theme
        if theme == "light":
            setTheme(Theme.LIGHT)
        elif theme == "dark":
            setTheme(Theme.DARK)
        else:
            setTheme(Theme.AUTO)

    def _on_names_changed(self, names: list):
        """名单变更回调"""
        self._name_manager_random.update_names(names)
        self._name_manager_dedup.update_names(names)
        logger.info("名单已同步更新到所有管理器")

    def _on_theme_changed(self, value: str):
        """主题变更回调"""
        self._config.theme = value
        self._apply_theme()

    def _on_interval_changed(self, interval: int):
        """闪动间隔变更回调"""
        self.randomPage.set_animation_interval(interval)
        self.dedupPage.set_animation_interval(interval)

    def _on_pick_count_changed(self, count: int):
        """抽取人数变更回调"""
        self._name_manager_random.pick_count = count
        self._name_manager_dedup.pick_count = count
        self._config.pick_count = count

    def _on_right_panel_collapse(self, collapsed: bool):
        """右栏收缩/展开回调"""
        pass

    def _on_nav_mode_changed(self, mode):
        """导航栏显示模式变更"""
        pass

    def switchTo(self, interface):
        """切换页面时控制右栏可见性"""
        super().switchTo(interface)
        if interface == self.settingsPage:
            self.rightPanel.setVisible(False)
        else:
            self.rightPanel.setVisible(True)

    def closeEvent(self, e):
        """窗口关闭事件"""
        logger.info("LuckyCall 窗口关闭")
        super().closeEvent(e)

    def mousePressEvent(self, e):
        """点击窗口任意位置清除右栏 SpinBox 焦点"""
        self.rightPanel.spinBox.clearFocus()
        super().mousePressEvent(e)
