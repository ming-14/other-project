"""!
@file core/plugin.py
@brief 插件系统

提供插件加载、生命周期管理与依赖解析。
插件通过实现Plugin接口注册扩展功能。
"""

from abc import ABC, abstractmethod
from typing import Optional
from core.logging import log_manager

_logger = log_manager.get_logger('core.plugin')


class Plugin(ABC):
    """!@brief 插件协议

    所有插件必须实现此接口。插件通过on_load注册组件/订阅事件，
    通过on_unload清理资源/取消订阅。
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """!@brief 插件唯一标识名"""
        ...

    @property
    def version(self) -> str:
        """!@brief 插件版本号"""
        return '1.0.0'

    @property
    def description(self) -> str:
        """!@brief 插件描述"""
        return ''

    @property
    def dependencies(self) -> list[str]:
        """!@brief 依赖的其他插件名列表"""
        return []

    @abstractmethod
    def on_load(self, context: 'PluginContext') -> None:
        """!@brief 插件加载

        @param context 插件上下文，提供API访问
        """
        ...

    @abstractmethod
    def on_unload(self, context: 'PluginContext') -> None:
        """!@brief 插件卸载"""
        ...

    def on_enable(self) -> None:
        """!@brief 插件启用（可选覆盖）"""
        pass

    def on_disable(self) -> None:
        """!@brief 插件禁用（可选覆盖）"""
        pass


class PluginContext:
    """!@brief 插件上下文

    提供插件访问引擎核心API的入口。
    """

    def __init__(self, engine: 'Engine'):
        self._engine = engine

    @property
    def engine(self) -> 'Engine':
        """!@brief 获取引擎实例"""
        return self._engine

    @property
    def events(self):
        """!@brief 获取事件总线"""
        return self._engine.events

    @property
    def registry(self):
        """!@brief 获取组件注册表"""
        return self._engine.registry

    @property
    def settings(self):
        """!@brief 获取设置管理器"""
        return self._engine.settings

    @property
    def world(self):
        """!@brief 获取世界管理器"""
        return self._engine.world_manager

    @property
    def renderer(self):
        """!@brief 获取渲染管线"""
        return self._engine.render_pipeline

    @property
    def input_system(self):
        """!@brief 获取输入系统"""
        return self._engine.input_system

    @property
    def player(self):
        """!@brief 获取玩家实体"""
        return self._engine.player

    def get_plugin(self, name: str) -> Optional[Plugin]:
        """!@brief 获取已加载的其他插件"""
        return self._engine.plugin_manager.get_plugin(name)


class PluginManager:
    """!@brief 插件管理器

    管理插件的加载、卸载、启用、禁用与依赖解析。
    """

    def __init__(self):
        self._plugins: dict[str, Plugin] = {}
        self._loaded_order: list[str] = []
        self._enabled: set[str] = set()
        self._context: Optional[PluginContext] = None

    def initialize(self, context: PluginContext) -> None:
        """!@brief 初始化插件管理器，绑定引擎上下文"""
        self._context = context

    def register(self, plugin: Plugin) -> bool:
        """!@brief 注册插件（不加载）

        @return True表示注册成功
        """
        name = plugin.name
        if name in self._plugins:
            _logger.warning('插件 "%s" 已注册，跳过', name)
            return False
        self._plugins[name] = plugin
        _logger.info('插件注册: %s v%s', name, plugin.version)
        return True

    def load(self, name: str) -> bool:
        """!@brief 加载指定插件（含依赖解析）"""
        plugin = self._plugins.get(name)
        if plugin is None:
            _logger.error('插件 "%s" 未注册', name)
            return False
        if name in self._loaded_order:
            _logger.warning('插件 "%s" 已加载', name)
            return True
        for dep in plugin.dependencies:
            if dep not in self._loaded_order:
                if not self.load(dep):
                    _logger.error('插件 "%s" 依赖 "%s" 加载失败', name, dep)
                    return False
        try:
            plugin.on_load(self._context)
            self._loaded_order.append(name)
            _logger.info('插件加载: %s v%s', name, plugin.version)
            return True
        except Exception as e:
            _logger.error('插件加载失败: %s: %s', name, e)
            return False

    def unload(self, name: str) -> bool:
        """!@brief 卸载指定插件"""
        if name not in self._loaded_order:
            return False
        plugin = self._plugins.get(name)
        if plugin is None:
            return False
        dependents = [n for n in self._loaded_order
                      if name in self._plugins.get(n, Plugin()).dependencies
                      if n != name]
        if dependents:
            _logger.error('插件 "%s" 被依赖: %s', name, dependents)
            return False
        try:
            if name in self._enabled:
                plugin.on_disable()
                self._enabled.discard(name)
            plugin.on_unload(self._context)
            self._loaded_order.remove(name)
            _logger.info('插件卸载: %s', name)
            return True
        except Exception as e:
            _logger.error('插件卸载失败: %s: %s', name, e)
            return False

    def enable(self, name: str) -> bool:
        """!@brief 启用已加载的插件"""
        if name not in self._loaded_order:
            return False
        if name in self._enabled:
            return True
        plugin = self._plugins[name]
        try:
            plugin.on_enable()
            self._enabled.add(name)
            return True
        except Exception as e:
            _logger.error('插件启用失败: %s: %s', name, e)
            return False

    def disable(self, name: str) -> bool:
        """!@brief 禁用已启用的插件"""
        if name not in self._enabled:
            return False
        plugin = self._plugins[name]
        try:
            plugin.on_disable()
            self._enabled.discard(name)
            return True
        except Exception as e:
            _logger.error('插件禁用失败: %s: %s', name, e)
            return False

    def get_plugin(self, name: str) -> Optional[Plugin]:
        """!@brief 获取已注册的插件"""
        return self._plugins.get(name)

    @property
    def loaded_plugins(self) -> list[str]:
        """!@brief 已加载插件名列表"""
        return list(self._loaded_order)

    @property
    def enabled_plugins(self) -> list[str]:
        """!@brief 已启用插件名列表"""
        return list(self._enabled)

    def load_all(self) -> None:
        """!@brief 加载所有已注册插件"""
        for name in list(self._plugins.keys()):
            self.load(name)

    def unload_all(self) -> None:
        """!@brief 按反序卸载所有插件"""
        for name in reversed(list(self._loaded_order)):
            self.unload(name)
