"""日志模块

基于 Python 标准库 logging 的轻量级日志封装。
提供模块级日志器获取函数，所有模块共享统一的日志配置。
日志仅写入文件，禁止输出到控制台。
"""

from __future__ import annotations

import logging
import os

_LOG_FORMAT = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    "data",
)
LOG_FILE = os.path.join(_DATA_DIR, "aipool.log")

_root_logger = logging.getLogger("aipool")
_root_logger.setLevel(logging.DEBUG)

os.makedirs(_DATA_DIR, exist_ok=True)

_file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
_file_handler.setLevel(logging.DEBUG)
_file_handler.setFormatter(logging.Formatter(_LOG_FORMAT, _DATE_FORMAT))
_root_logger.addHandler(_file_handler)


def get_logger(name: str) -> logging.Logger:
    """获取模块级日志器

    Args:
        name: 模块名（如 "PoolManager", "SettingsManager"）

    Returns:
        绑定到 aipool 命名空间的 Logger 实例
    """
    return _root_logger.getChild(name)
