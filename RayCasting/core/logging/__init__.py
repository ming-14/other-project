"""!
@file core/logging/__init__.py
@brief 日志系统包

导出日志管理器便捷接口，保持向后兼容。
"""

from core.logging.log_config import LogConfig, HandlerConfig, sanitize_path
from core.logging.log_manager import LogManager, get_manager, setup, get_logger, shutdown

__all__ = [
    'LogConfig', 'HandlerConfig', 'sanitize_path',
    'LogManager', 'get_manager', 'setup', 'get_logger', 'shutdown',
]
