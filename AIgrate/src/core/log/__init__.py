"""日志子包

提供标准库 logging 封装的模块级日志器获取函数。
"""

from core.log.logger import get_logger

__all__ = [
    "get_logger",
]