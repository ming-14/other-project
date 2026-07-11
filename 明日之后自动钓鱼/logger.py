# -*- coding: utf-8 -*-
"""
@file       logger.py
@brief      简洁日志模块
@details    同时输出到控制台和文件，标准日志格式
"""

import sys
import os
from datetime import datetime
from typing import Optional


class Logger:
    LOG_FORMAT = "%Y-%m-%d %H:%M:%S"
    LEVEL_DEBUG = 0
    LEVEL_INFO = 1
    LEVEL_WARNING = 2
    LEVEL_ERROR = 3

    def __init__(self, log_file: Optional[str] = None, level: int = LEVEL_INFO):
        self.level = level
        self.log_file = log_file
        if log_file:
            log_dir = os.path.dirname(log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir)
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(f"\n{'='*50}\n")
                f.write(f"Session started: {datetime.now().strftime(self.LOG_FORMAT)}\n")
                f.write(f"{'='*50}\n")

    def _format(self, level_str: str, msg: str) -> str:
        timestamp = datetime.now().strftime(self.LOG_FORMAT)
        return f"[{timestamp}] [{level_str}] {msg}"

    def _output(self, level_str: str, msg: str) -> None:
        formatted = self._format(level_str, msg)
        print(formatted)
        if self.log_file:
            try:
                with open(self.log_file, 'a', encoding='utf-8') as f:
                    f.write(formatted + "\n")
            except Exception:
                pass

    def debug(self, msg: str) -> None:
        if self.level <= self.LEVEL_DEBUG:
            self._output("DEBUG", msg)

    def info(self, msg: str) -> None:
        if self.level <= self.LEVEL_INFO:
            self._output("INFO", msg)

    def warning(self, msg: str) -> None:
        if self.level <= self.LEVEL_WARNING:
            self._output("WARN", msg)

    def error(self, msg: str) -> None:
        if self.level <= self.LEVEL_ERROR:
            self._output("ERROR", msg)


_default_logger: Optional[Logger] = None


def init_logger(log_file: Optional[str] = None, level: int = Logger.LEVEL_INFO) -> Logger:
    global _default_logger
    _default_logger = Logger(log_file, level)
    return _default_logger


def get_logger() -> Logger:
    global _default_logger
    if _default_logger is None:
        _default_logger = Logger()
    return _default_logger
