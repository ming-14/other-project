"""!
@file core/settings.py
@brief 运行时设置管理器

提供可变的运行时配置管理，支持分组、观察者回调、
运行时修改与持久化。与config.py（不可变常量）互补。
"""

import json
import os
from typing import Any, Callable, Optional
from core import log_manager

_logger = log_manager.get_logger('core.settings')


class SettingsGroup:
    """!@brief 设置分组

    管理一组相关设置项，支持默认值、范围校验和变更回调。
    """

    def __init__(self, name: str):
        self._name = name
        self._values: dict[str, Any] = {}
        self._defaults: dict[str, Any] = {}
        self._validators: dict[str, Callable[[Any], bool]] = {}
        self._callbacks: dict[str, list[Callable[[str, Any, Any], None]]] = {}

    @property
    def name(self) -> str:
        return self._name

    def define(self, key: str, default: Any,
               validator: Optional[Callable[[Any], bool]] = None) -> None:
        """!@brief 定义设置项

        @param key       设置键名
        @param default   默认值
        @param validator 可选校验函数，返回True表示值合法
        """
        self._defaults[key] = default
        if key not in self._values:
            self._values[key] = default
        if validator is not None:
            self._validators[key] = validator

    def get(self, key: str, default: Any = None) -> Any:
        """!@brief 获取设置值"""
        return self._values.get(key, default)

    def set(self, key: str, value: Any) -> bool:
        """!@brief 设置值，通过校验后触发回调

        @return True表示设置成功
        """
        validator = self._validators.get(key)
        if validator is not None and not validator(value):
            _logger.warning('设置 %s.%s 值校验失败: %s', self._name, key, value)
            return False
        old = self._values.get(key)
        self._values[key] = value
        if old != value:
            self._fire_change(key, old, value)
        return True

    def on_change(self, key: str, callback: Callable[[str, Any, Any], None]) -> None:
        """!@brief 注册设置变更回调

        @param key      设置键名
        @param callback 回调函数 (key, old_value, new_value)
        """
        if key not in self._callbacks:
            self._callbacks[key] = []
        self._callbacks[key].append(callback)

    def reset(self, key: str) -> None:
        """!@brief 重置为默认值"""
        if key in self._defaults:
            self.set(key, self._defaults[key])

    def reset_all(self) -> None:
        """!@brief 重置所有设置为默认值"""
        for key in list(self._defaults.keys()):
            self.set(key, self._defaults[key])

    def _fire_change(self, key: str, old: Any, new: Any) -> None:
        for cb in self._callbacks.get(key, []):
            try:
                cb(key, old, new)
            except Exception as e:
                _logger.error('设置回调异常: %s.%s: %s', self._name, key, e)

    def to_dict(self) -> dict:
        return dict(self._values)

    def from_dict(self, data: dict) -> None:
        for k, v in data.items():
            if k in self._defaults:
                self.set(k, v)


class SettingsManager:
    """!@brief 运行时设置管理器

    管理多个设置分组，提供全局查询、持久化接口。
    """

    def __init__(self):
        self._groups: dict[str, SettingsGroup] = {}

    def group(self, name: str) -> SettingsGroup:
        """!@brief 获取或创建设置分组"""
        if name not in self._groups:
            self._groups[name] = SettingsGroup(name)
        return self._groups[name]

    def get(self, group: str, key: str, default: Any = None) -> Any:
        """!@brief 快捷获取设置值"""
        g = self._groups.get(group)
        if g is not None:
            return g.get(key, default)
        return default

    def set(self, group: str, key: str, value: Any) -> bool:
        """!@brief 快捷设置值"""
        g = self._groups.get(group)
        if g is not None:
            return g.set(key, value)
        return False

    def on_change(self, group: str, key: str,
                  callback: Callable[[str, Any, Any], None]) -> None:
        """!@brief 快捷注册变更回调"""
        self.group(group).on_change(key, callback)

    def to_dict(self) -> dict:
        return {name: g.to_dict() for name, g in self._groups.items()}

    def from_dict(self, data: dict) -> None:
        for name, values in data.items():
            g = self.group(name)
            g.from_dict(values)

    def save_to_file(self, filepath: str) -> bool:
        """!@brief 保存设置到JSON文件"""
        try:
            os.makedirs(os.path.dirname(filepath) or '.', exist_ok=True)
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            _logger.error('保存设置失败: %s', e)
            return False

    def load_from_file(self, filepath: str) -> bool:
        """!@brief 从JSON文件加载设置"""
        try:
            if not os.path.isfile(filepath):
                return False
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.from_dict(data)
            return True
        except Exception as e:
            _logger.error('加载设置失败: %s', e)
            return False


_manager: Optional[SettingsManager] = None


def get_settings() -> SettingsManager:
    """!@brief 获取全局设置管理器"""
    global _manager
    if _manager is None:
        _manager = SettingsManager()
    return _manager
