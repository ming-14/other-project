"""i18n 包 - 国际化支持

提供多语言翻译、语言切换与系统语言检测功能。

核心接口:
  - t(key, **kwargs): 翻译便捷函数
  - I18nManager: 国际化管理器（单例）
  - i18n_manager: 模块级单例实例
"""

from core.i18n.manager import I18nManager, i18n_manager
from core.i18n.translate import t

__all__ = [
    "I18nManager",
    "i18n_manager",
    "t",
]