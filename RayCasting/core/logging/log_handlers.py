"""!
@file core/log_handlers.py
@brief 日志输出目标管理

封装Python logging各种Handler的创建、格式器绑定与生命周期管理。
"""

import logging
import logging.handlers
import os
import sys

from core.logging.log_config import HandlerConfig, _DEFAULT_FORMAT, _DEFAULT_DATE_FORMAT


class LogHandlerFactory:
    """!@brief 输出目标工厂"""

    @staticmethod
    def create(config: HandlerConfig) -> logging.Handler:
        """!@brief 根据配置创建Handler

        @param config 输出目标配置
        @return logging.Handler 实例，创建失败时返回 NullHandler
        """
        try:
            if config.type == 'console':
                handler = LogHandlerFactory._create_console_handler(config)
            elif config.type == 'file':
                handler = LogHandlerFactory._create_file_handler(config)
            else:
                sys.stderr.write('未知的输出目标类型: %s\n' % config.type)
                return logging.NullHandler()
            level_name = config.level if config.level else None
            if level_name:
                handler.setLevel(getattr(logging, level_name, logging.NOTSET))
            formatter = LogHandlerFactory._create_formatter(
                config.format, config.date_format)
            handler.setFormatter(formatter)
            return handler
        except Exception as e:
            sys.stderr.write('创建输出目标失败: %s (%s)\n' % (config.type, e))
            return logging.NullHandler()

    @staticmethod
    def _create_console_handler(config: HandlerConfig) -> logging.StreamHandler:
        """!@brief 创建控制台输出Handler（输出到stderr）"""
        handler = logging.StreamHandler(sys.stderr)
        return handler

    @staticmethod
    def _create_file_handler(config: HandlerConfig) -> logging.Handler:
        """!@brief 创建文件输出Handler（支持轮转）"""
        log_dir = os.path.dirname(config.filepath)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        if config.rotation_type == 'size':
            return logging.handlers.RotatingFileHandler(
                config.filepath,
                maxBytes=config.max_bytes,
                backupCount=config.backup_count,
                encoding='utf-8',
            )
        elif config.rotation_type == 'time':
            return logging.handlers.TimedRotatingFileHandler(
                config.filepath,
                when=config.when,
                backupCount=config.backup_count,
                encoding='utf-8',
            )
        else:
            return logging.FileHandler(
                config.filepath,
                encoding='utf-8',
            )

    @staticmethod
    def _create_formatter(fmt: str, datefmt: str) -> logging.Formatter:
        """!@brief 创建格式器，格式无效时回退默认"""
        try:
            return logging.Formatter(fmt=fmt, datefmt=datefmt)
        except Exception:
            return logging.Formatter(
                fmt=_DEFAULT_FORMAT, datefmt=_DEFAULT_DATE_FORMAT)


class LogHandlerManager:
    """!@brief 输出目标生命周期管理"""

    def __init__(self):
        self._handlers: dict[str, logging.Handler] = {}
        self._factory: LogHandlerFactory = LogHandlerFactory()

    @staticmethod
    def _make_key(config: HandlerConfig) -> str:
        """!@brief 生成Handler标识键"""
        if config.type == 'console':
            return 'console'
        return 'file:%s' % config.filepath

    def apply(self, logger: logging.Logger,
              handler_configs: list[HandlerConfig]) -> None:
        """!@brief 将配置的输出目标应用到日志器

        先移除旧Handler，再逐个创建并添加新Handler。

        @param logger          目标日志器
        @param handler_configs 输出目标配置列表
        """
        self.remove_all(logger)
        for hc in handler_configs:
            self.add_handler(logger, hc)

    def add_handler(self, logger: logging.Logger,
                    config: HandlerConfig) -> str:
        """!@brief 添加单个输出目标

        @param logger 目标日志器
        @param config 输出目标配置
        @return Handler标识键
        """
        key = self._make_key(config)
        if key in self._handlers:
            self.remove_handler(logger, key)
        handler = self._factory.create(config)
        self._handlers[key] = handler
        logger.addHandler(handler)
        return key

    def remove_handler(self, logger: logging.Logger,
                       handler_key: str) -> None:
        """!@brief 移除指定输出目标

        @param logger      目标日志器
        @param handler_key Handler标识键
        """
        handler = self._handlers.pop(handler_key, None)
        if handler is not None:
            logger.removeHandler(handler)
            try:
                handler.close()
            except Exception:
                pass

    def remove_all(self, logger: logging.Logger) -> None:
        """!@brief 移除所有输出目标"""
        for key in list(self._handlers.keys()):
            self.remove_handler(logger, key)

    def get_handler_keys(self) -> list[str]:
        """!@brief 获取当前所有输出目标标识"""
        return list(self._handlers.keys())