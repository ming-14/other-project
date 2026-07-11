"""!
@file core/log_manager.py
@brief 日志管理器（单例入口）

提供日志系统初始化、模块日志器获取、配置热加载、
运行时状态查询等全局接口。
"""

import logging
import os
import re
import sys

from core.logging.log_config import LogConfig, HandlerConfig, sanitize_path
from core.logging.log_handlers import LogHandlerManager
from core.logging.log_async import AsyncLogWriter
from core.logging.log_qt_bridge import QtLogBridge

_LOG_ROOT_NAME = 'raycasting'

_INVALID_LOGGER_CHARS = re.compile(r'[^a-zA-Z0-9_.]')


class LogManager:
    """!@brief 日志管理器（单例入口）

    提供日志系统初始化、模块日志器获取、配置热加载、
    运行时状态查询等全局接口。
    """

    def __init__(self):
        self._root_logger: logging.Logger = logging.getLogger(_LOG_ROOT_NAME)
        self._config: LogConfig = LogConfig.default()
        self._handler_mgr: LogHandlerManager = LogHandlerManager()
        self._async_writer: AsyncLogWriter | None = None
        self._qt_bridge: QtLogBridge | None = None
        self._initialized: bool = False

    def setup(self, config: LogConfig | None = None,
              config_path: str | None = None) -> None:
        """!@brief 初始化日志系统

        @param config      代码配置对象，优先级最高
        @param config_path 配置文件路径，次优先级
        两者均未提供时使用默认配置。
        """
        if self._initialized:
            return

        file_config = None
        if config_path:
            file_config = LogConfig.load_from_file(config_path)

        if config:
            merged = LogConfig.default().merge(file_config).merge(config)
        elif file_config:
            merged = LogConfig.default().merge(file_config)
        else:
            merged = LogConfig.default()

        errors = merged.validate()
        if errors:
            for e in errors:
                sys.stderr.write('日志配置校验错误: %s\n' % e)
            merged = LogConfig.default()

        self._config = merged

        self._root_logger.setLevel(
            getattr(logging, merged.global_level, logging.WARNING))
        self._root_logger.propagate = False

        if not merged.handlers:
            merged.handlers = [HandlerConfig(type='console', level='WARNING')]

        if merged.async_enabled and len(merged.handlers) > 0:
            actual_handlers = []
            for hc in merged.handlers:
                handler = self._handler_mgr._factory.create(hc)
                actual_handlers.append(handler)
            self._async_writer = AsyncLogWriter(
                actual_handlers, queue_size=merged.async_queue_size)
            self._async_writer.start()
            self._root_logger.addHandler(self._async_writer.get_handler())
            for h in actual_handlers:
                try:
                    h.close()
                except Exception:
                    pass
        else:
            self._handler_mgr.apply(self._root_logger, merged.handlers)

        self._qt_bridge = QtLogBridge(self._root_logger)
        self._qt_bridge.install()

        for mod, level in merged.module_levels.items():
            mod_logger = logging.getLogger('%s.%s' % (_LOG_ROOT_NAME, mod))
            mod_logger.setLevel(
                getattr(logging, level, logging.NOTSET))

        self._setup_legacy_loggers()

        self._initialized = True

    def _setup_legacy_loggers(self) -> None:
        """!@brief 将旧日志器纳入统一管理"""
        legacy_logger = logging.getLogger('win32_output')
        legacy_logger.parent = self._root_logger
        legacy_logger.propagate = True

    def get_logger(self, name: str) -> logging.Logger:
        """!@brief 获取模块日志器

        @param name 模块路径名（如 'world.maze'），
                    自动添加应用根前缀 'raycasting.'
        @return logging.Logger 实例
        """
        if not name:
            return self._root_logger
        safe_name = _INVALID_LOGGER_CHARS.sub('_', name)
        return logging.getLogger('%s.%s' % (_LOG_ROOT_NAME, safe_name))

    def set_level(self, level: str, module: str | None = None) -> None:
        """!@brief 动态设置日志级别

        @param level  日志级别字符串
        @param module 模块名，为None时设置全局级别
        """
        if level not in ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'):
            sys.stderr.write('无效的日志级别: %s\n' % level)
            return
        if module:
            mod_logger = logging.getLogger('%s.%s' % (_LOG_ROOT_NAME, module))
            mod_logger.setLevel(getattr(logging, level))
            if module not in self._config.module_levels:
                self._config.module_levels[module] = level
            else:
                self._config.module_levels[module] = level
        else:
            self._root_logger.setLevel(getattr(logging, level))
            self._config.global_level = level

    def add_handler(self, handler_config: HandlerConfig) -> None:
        """!@brief 运行时添加输出目标

        @param handler_config 输出目标配置
        """
        if self._async_writer and not self._async_writer.is_fallback:
            sys.stderr.write('异步写入模式下不支持运行时添加输出目标\n')
            return
        self._handler_mgr.add_handler(self._root_logger, handler_config)

    def remove_handler(self, handler_key: str) -> None:
        """!@brief 运行时移除输出目标

        @param handler_key 输出目标标识
        """
        if self._async_writer and not self._async_writer.is_fallback:
            sys.stderr.write('异步写入模式下不支持运行时移除输出目标\n')
            return
        self._handler_mgr.remove_handler(self._root_logger, handler_key)

    def reload_config(self, config_path: str | None = None) -> None:
        """!@brief 重新加载配置文件并应用

        @param config_path 配置文件路径
        """
        if not self._initialized:
            return
        self.shutdown()
        self.setup(config_path=config_path)

    def get_status(self) -> dict:
        """!@brief 查询日志系统运行状态

        @return 包含全局级别、模块级别、已启用输出目标等信息的字典
        """
        return {
            'initialized': self._initialized,
            'global_level': self._config.global_level,
            'module_levels': dict(self._config.module_levels),
            'handlers': self._handler_mgr.get_handler_keys(),
            'async_enabled': self._config.async_enabled,
            'async_queue_size': (self._async_writer.queue_size
                                 if self._async_writer else 0),
            'qt_bridge_available': (self._qt_bridge.available
                                    if self._qt_bridge else False),
        }

    def subscribe_events(self, event_bus) -> None:
        """!@brief 订阅EventBus事件

        @param event_bus EventBus实例
        """
        try:
            from core.event_bus import EventType
            event_bus.subscribe(EventType.GAME_STATE_CHANGE,
                                self._on_state_change)
            event_bus.subscribe(EventType.GAME_EXIT_REACHED,
                                self._on_exit_reached)
        except Exception:
            pass

    def _on_state_change(self, data: dict | None) -> None:
        """!@brief 游戏状态变更回调"""
        if data:
            logger = self.get_logger('core.game')
            logger.info('游戏状态变更: %s -> %s',
                        data.get('from', '?'), data.get('to', '?'))

    def _on_exit_reached(self, data: dict | None) -> None:
        """!@brief 玩家到达出口回调"""
        if data:
            logger = self.get_logger('core.game')
            logger.info('玩家到达出口: (%s, %s)',
                        data.get('x', '?'), data.get('y', '?'))

    def shutdown(self) -> None:
        """!@brief 关闭日志系统，等待异步队列排空"""
        if not self._initialized:
            return
        if self._qt_bridge:
            self._qt_bridge.uninstall()
            self._qt_bridge = None
        if self._async_writer:
            self._async_writer.stop(timeout=self._config.shutdown_timeout)
            if self._async_writer.is_fallback:
                for h in self._async_writer.get_direct_handlers():
                    try:
                        self._root_logger.removeHandler(h)
                    except Exception:
                        pass
            else:
                qh = self._async_writer.get_handler()
                self._root_logger.removeHandler(qh)
            self._async_writer = None
        self._handler_mgr.remove_all(self._root_logger)
        self._initialized = False


_manager: LogManager | None = None


def get_manager() -> LogManager:
    """!@brief 获取全局日志管理器实例"""
    global _manager
    if _manager is None:
        _manager = LogManager()
    return _manager


def setup(config: LogConfig | None = None,
          config_path: str | None = None) -> None:
    """!@brief 初始化日志系统（便捷接口）"""
    get_manager().setup(config=config, config_path=config_path)


def get_logger(name: str) -> logging.Logger:
    """!@brief 获取模块日志器（便捷接口）"""
    return get_manager().get_logger(name)


def shutdown() -> None:
    """!@brief 关闭日志系统（便捷接口）"""
    get_manager().shutdown()