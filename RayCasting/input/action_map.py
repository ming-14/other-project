"""!
@file input/action_map.py
@brief 动作映射系统

提供可配置的输入动作映射，支持自定义动作绑定与回调。
"""

from typing import Callable, Optional
from core import log_manager

_logger = log_manager.get_logger('input.action_map')


class ActionMap:
    """!@brief 动作映射

    管理输入动作名称到回调函数的映射。
    支持运行时绑定/解绑动作。
    """

    def __init__(self):
        self._bindings: dict[str, list[Callable[[bool], None]]] = {}
        self._action_states: dict[str, bool] = {}

    def bind(self, action: str, callback: Callable[[bool], None]) -> None:
        """!@brief 绑定动作回调

        @param action   动作名称
        @param callback 回调函数 callback(pressed: bool)
        """
        if action not in self._bindings:
            self._bindings[action] = []
        self._bindings[action].append(callback)

    def unbind(self, action: str, callback: Optional[Callable] = None) -> None:
        """!@brief 解绑动作回调

        @param action   动作名称
        @param callback 指定回调，为None时解绑所有
        """
        if action not in self._bindings:
            return
        if callback is None:
            del self._bindings[action]
        else:
            self._bindings[action] = [
                cb for cb in self._bindings[action] if cb != callback]

    def process_actions(self, actions: dict[str, bool]) -> None:
        """!@brief 处理动作状态变更并触发回调

        @param actions 动作名到按下状态的映射
        """
        for action, pressed in actions.items():
            old = self._action_states.get(action, False)
            self._action_states[action] = pressed
            if pressed != old or pressed:
                for cb in self._bindings.get(action, []):
                    try:
                        cb(pressed)
                    except Exception as e:
                        _logger.error('动作回调异常: %s: %s', action, e)

    def is_active(self, action: str) -> bool:
        """!@brief 查询动作是否激活"""
        return self._action_states.get(action, False)

    @property
    def actions(self) -> list[str]:
        """!@brief 所有已注册动作名"""
        return list(self._action_states.keys())

    def clear(self) -> None:
        """!@brief 清空所有绑定"""
        self._bindings.clear()
        self._action_states.clear()
