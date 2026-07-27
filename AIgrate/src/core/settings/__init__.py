"""设置管理子包

提供应用设置的加载、保存与默认值管理。
"""

from core.settings.manager import SettingsManager, settings_manager

__all__ = [
    "SettingsManager",
    "settings_manager",
]