"""!
@file core/engine/__init__.py
@brief 引擎主控包

导出引擎核心类。
"""

from core.engine.game import Engine, Game
from core.engine.api import EngineAPI
from core.engine.plugin import Plugin, PluginContext, PluginManager

__all__ = ['Engine', 'Game', 'EngineAPI', 'Plugin', 'PluginContext', 'PluginManager']
