"""!
@file core/log_config.py
@brief 日志配置数据模型

定义日志系统的配置数据结构、校验逻辑与文件加载。
配置优先级：代码参数 > 配置文件 > 默认值。
"""

import json
import os
import sys
from dataclasses import dataclass, field

_VALID_LEVELS = frozenset({'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'})
_VALID_ROTATION_TYPES = frozenset({'size', 'time', 'none'})
_VALID_TIME_WHEN = frozenset({'H', 'D', 'W', 'M'})

_DEFAULT_FORMAT = '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
_DEFAULT_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'


@dataclass
class HandlerConfig:
    """!@brief 单个输出目标配置"""

    type: str = 'console'
    level: str = ''
    format: str = _DEFAULT_FORMAT
    date_format: str = _DEFAULT_DATE_FORMAT
    filepath: str = 'logs/game.log'
    rotation_type: str = 'size'
    max_bytes: int = 10485760
    backup_count: int = 3
    when: str = 'D'

    def validate(self) -> list[str]:
        """!@brief 校验配置合法性

        @return 错误信息列表，空列表表示校验通过
        """
        errors = []
        if self.type not in ('console', 'file'):
            errors.append('输出目标类型无效: %s, 仅支持 console/file' % self.type)
        if self.level and self.level not in _VALID_LEVELS:
            errors.append('输出目标级别无效: %s' % self.level)
        if self.type == 'file':
            if self.rotation_type not in _VALID_ROTATION_TYPES:
                errors.append('轮转类型无效: %s' % self.rotation_type)
            if self.rotation_type == 'time' and self.when not in _VALID_TIME_WHEN:
                errors.append('时间轮转参数无效: %s' % self.when)
            if self.rotation_type == 'size' and self.max_bytes <= 0:
                errors.append('轮转大小必须大于0: %d' % self.max_bytes)
            if self.backup_count < 0:
                errors.append('备份数不能为负: %d' % self.backup_count)
        return errors


@dataclass
class LogConfig:
    """!@brief 日志系统完整配置"""

    global_level: str = 'WARNING'
    module_levels: dict[str, str] = field(default_factory=dict)
    handlers: list[HandlerConfig] = field(default_factory=list)
    async_enabled: bool = True
    async_queue_size: int = 1000
    shutdown_timeout: float = 5.0

    def validate(self) -> list[str]:
        """!@brief 校验配置合法性

        @return 错误信息列表，空列表表示校验通过
        """
        errors = []
        if self.global_level not in _VALID_LEVELS:
            errors.append('全局日志级别无效: %s' % self.global_level)
        for mod, level in self.module_levels.items():
            if level not in _VALID_LEVELS:
                errors.append('模块 %s 日志级别无效: %s' % (mod, level))
        for i, hc in enumerate(self.handlers):
            for e in hc.validate():
                errors.append('输出目标[%d]: %s' % (i, e))
        if self.async_queue_size <= 0:
            errors.append('异步队列大小必须大于0: %d' % self.async_queue_size)
        if self.shutdown_timeout < 0:
            errors.append('关闭超时不能为负: %.1f' % self.shutdown_timeout)
        return errors

    @staticmethod
    def from_dict(data: dict) -> 'LogConfig':
        """!@brief 从字典创建配置对象

        @param data 配置字典
        @return LogConfig 对象
        """
        handlers = []
        for hd in data.get('handlers', []):
            handlers.append(HandlerConfig(
                type=hd.get('type', 'console'),
                level=hd.get('level', ''),
                format=hd.get('format', _DEFAULT_FORMAT),
                date_format=hd.get('date_format', _DEFAULT_DATE_FORMAT),
                filepath=hd.get('filepath', 'logs/game.log'),
                rotation_type=hd.get('rotation_type', 'size'),
                max_bytes=hd.get('max_bytes', 10485760),
                backup_count=hd.get('backup_count', 3),
                when=hd.get('when', 'D'),
            ))
        return LogConfig(
            global_level=data.get('global_level', 'WARNING'),
            module_levels=dict(data.get('module_levels', {})),
            handlers=handlers,
            async_enabled=data.get('async_enabled', True),
            async_queue_size=data.get('async_queue_size', 1000),
            shutdown_timeout=data.get('shutdown_timeout', 5.0),
        )

    @staticmethod
    def load_from_file(filepath: str) -> 'LogConfig':
        """!@brief 从JSON文件加载配置

        @param filepath 配置文件路径
        @return LogConfig 对象，解析失败时返回默认配置
        """
        if not os.path.isfile(filepath):
            sys.stderr.write('日志配置文件不存在: %s, 使用默认配置\n' % filepath)
            return LogConfig.default()
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.loads(f.read())
        except json.JSONDecodeError:
            sys.stderr.write('日志配置文件格式错误: %s, 使用默认配置\n' % filepath)
            return LogConfig.default()
        except UnicodeDecodeError:
            sys.stderr.write('日志配置文件编码错误: %s, 使用默认配置\n' % filepath)
            return LogConfig.default()
        except Exception as e:
            sys.stderr.write('日志配置文件读取失败: %s (%s), 使用默认配置\n' % (filepath, e))
            return LogConfig.default()
        return LogConfig.from_dict(data)

    def merge(self, other: 'LogConfig | None') -> 'LogConfig':
        """!@brief 合并配置，other 优先级高于 self

        @param other 高优先级配置
        @return 合并后的新配置
        """
        if other is None:
            return LogConfig(
                global_level=self.global_level,
                module_levels=dict(self.module_levels),
                handlers=list(self.handlers),
                async_enabled=self.async_enabled,
                async_queue_size=self.async_queue_size,
                shutdown_timeout=self.shutdown_timeout,
            )
        merged_levels = dict(self.module_levels)
        merged_levels.update(other.module_levels)
        handlers = list(self.handlers) if not other.handlers else list(other.handlers)
        return LogConfig(
            global_level=other.global_level if other.global_level != 'WARNING' else self.global_level,
            module_levels=merged_levels,
            handlers=handlers,
            async_enabled=other.async_enabled,
            async_queue_size=other.async_queue_size,
            shutdown_timeout=other.shutdown_timeout,
        )

    @staticmethod
    def default() -> 'LogConfig':
        """!@brief 创建默认配置（控制台WARNING级别）"""
        return LogConfig(
            global_level='WARNING',
            module_levels={},
            handlers=[
                HandlerConfig(
                    type='console',
                    level='WARNING',
                )
            ],
            async_enabled=True,
            async_queue_size=1000,
            shutdown_timeout=5.0,
        )


def sanitize_path(path: str) -> str:
    """!@brief 路径脱敏，将用户目录替换为~

    @param path 原始路径
    @return 脱敏后的路径
    """
    home = os.path.expanduser('~')
    if home and path.startswith(home):
        return '~' + path[len(home):]
    return path