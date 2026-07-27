"""翻译便捷函数

提供模块级 t() 函数作为 I18nManager.translate() 的快捷入口。
"""

from __future__ import annotations

from typing import Any

from core.i18n.manager import i18n_manager


def t(key: str, **kwargs: Any) -> str:
    """翻译函数 - 模块级便捷入口

    用法:
        t("pool.deleted", name="mypool")   # -> "已删除 [mypool]"
        t("repl.welcome.title")            # -> "AI 池 - 命令行交互版"

    Args:
        key:    翻译键
        kwargs: 命名占位符变量

    Returns:
        翻译后的文本
    """
    return i18n_manager.translate(key, **kwargs)