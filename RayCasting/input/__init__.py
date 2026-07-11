"""!
@file input/__init__.py
@brief 输入模块包

导出输入层核心类。
"""

from input.base import InputSystem, MouseInput
from input.action_map import ActionMap

__all__ = ['InputSystem', 'MouseInput', 'ActionMap']
