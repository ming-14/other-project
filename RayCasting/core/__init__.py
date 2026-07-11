"""!
@file core/__init__.py
@brief 核心模块包

导出核心基础设施类，保持向后兼容。
log_manager 通过直接导入子模块，避免循环依赖。
"""

import core.logging.log_manager as _log_manager
log_manager = _log_manager

from core.lifecycle import (Lifecycle, LifecycleMixin, Updatable,
                            Renderable, Tickable, Initializable)
from core.registry import ComponentRegistry, get_registry
from core.settings import SettingsManager, SettingsGroup, get_settings
from core.engine.plugin import Plugin, PluginContext, PluginManager
from core.engine.api import EngineAPI
from core.engine.game import Engine, Game
from core.event_bus import EventBus, EventType
from core.state_machine import StateMachine
from core.hud import HUD

__all__ = [
    'log_manager',
    'Lifecycle', 'LifecycleMixin', 'Updatable', 'Renderable',
    'Tickable', 'Initializable',
    'ComponentRegistry', 'get_registry',
    'SettingsManager', 'SettingsGroup', 'get_settings',
    'Plugin', 'PluginContext', 'PluginManager',
    'EngineAPI', 'Engine', 'Game',
    'EventBus', 'EventType',
    'StateMachine',
    'HUD',
]
