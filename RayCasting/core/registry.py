"""!
@file core/registry.py
@brief 组件注册表

提供全局组件注册、查找与生命周期管理。
支持按名称、类型、标签注册和查询组件。
"""

from typing import Any, TypeVar, Optional, Type
from core import log_manager

_logger = log_manager.get_logger('core.registry')

T = TypeVar('T')


class ComponentRegistry:
    """!@brief 组件注册表

    管理所有游戏组件的注册、查找与生命周期。
    支持名称注册、类型注册、标签分组。
    """

    def __init__(self):
        self._components: dict[str, Any] = {}
        self._by_type: dict[Type, list[str]] = {}
        self._by_tag: dict[str, list[str]] = {}
        self._tags: dict[str, set[str]] = {}

    def register(self, name: str, component: Any, *tags: str) -> None:
        """!@brief 注册组件

        @param name      组件唯一名称
        @param component 组件实例
        @param tags      可选标签，用于分组查询
        """
        if name in self._components:
            _logger.warning('组件 "%s" 已存在，将被覆盖', name)
            self.unregister(name)
        self._components[name] = component
        comp_type = type(component)
        if comp_type not in self._by_type:
            self._by_type[comp_type] = []
        self._by_type[comp_type].append(name)
        for tag in tags:
            if tag not in self._by_tag:
                self._by_tag[tag] = []
            self._by_tag[tag].append(name)
            if name not in self._tags:
                self._tags[name] = set()
            self._tags[name].add(tag)

    def unregister(self, name: str) -> None:
        """!@brief 注销组件"""
        if name not in self._components:
            return
        comp = self._components.pop(name)
        comp_type = type(comp)
        if comp_type in self._by_type:
            self._by_type[comp_type] = [
                n for n in self._by_type[comp_type] if n != name]
            if not self._by_type[comp_type]:
                del self._by_type[comp_type]
        if name in self._tags:
            for tag in self._tags[name]:
                if tag in self._by_tag:
                    self._by_tag[tag] = [
                        n for n in self._by_tag[tag] if n != name]
                    if not self._by_tag[tag]:
                        del self._by_tag[tag]
            del self._tags[name]

    def get(self, name: str) -> Optional[Any]:
        """!@brief 按名称获取组件"""
        return self._components.get(name)

    def get_typed(self, name: str, expected_type: Type[T]) -> Optional[T]:
        """!@brief 按名称获取组件并类型检查"""
        comp = self._components.get(name)
        if comp is not None and isinstance(comp, expected_type):
            return comp
        return None

    def find_by_type(self, comp_type: Type[T]) -> list[T]:
        """!@brief 按类型查找所有组件"""
        names = self._by_type.get(comp_type, [])
        result = []
        for n in names:
            comp = self._components.get(n)
            if comp is not None:
                result.append(comp)
        return result

    def find_by_tag(self, tag: str) -> list[Any]:
        """!@brief 按标签查找所有组件"""
        names = self._by_tag.get(tag, [])
        result = []
        for n in names:
            comp = self._components.get(n)
            if comp is not None:
                result.append(comp)
        return result

    def find_one_by_tag(self, tag: str) -> Optional[Any]:
        """!@brief 按标签查找第一个组件"""
        names = self._by_tag.get(tag, [])
        if names:
            return self._components.get(names[0])
        return None

    def has(self, name: str) -> bool:
        """!@brief 检查组件是否已注册"""
        return name in self._components

    @property
    def names(self) -> list[str]:
        """!@brief 所有已注册组件名称"""
        return list(self._components.keys())

    @property
    def count(self) -> int:
        """!@brief 已注册组件数量"""
        return len(self._components)

    def clear(self) -> None:
        """!@brief 清空所有注册"""
        self._components.clear()
        self._by_type.clear()
        self._by_tag.clear()
        self._tags.clear()


_registry: Optional[ComponentRegistry] = None


def get_registry() -> ComponentRegistry:
    """!@brief 获取全局组件注册表"""
    global _registry
    if _registry is None:
        _registry = ComponentRegistry()
    return _registry
