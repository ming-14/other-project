"""!
@file core/state_machine.py
@brief 通用状态机模块

管理游戏状态流转，提供状态注册、转换规则、
进入/退出回调与更新调度。
"""

from typing import Callable, Optional
from core import log_manager

_logger = log_manager.get_logger('core.state_machine')


class StateMachine:
    """!@brief 有限状态机

    管理状态注册、转换规则与当前状态查询。
    每个状态关联一个handler函数，update()调用当前状态的handler。
    支持进入/退出回调、转换守卫。
    """

    def __init__(self):
        self._states: dict[str, Callable] = {}
        self._transitions: dict[tuple[str, str], Optional[Callable]] = {}
        self._on_enter: dict[str, list[Callable]] = {}
        self._on_exit: dict[str, list[Callable]] = {}
        self._current: Optional[str] = None
        self._previous: Optional[str] = None

    def add_state(self, name: str, handler: Callable) -> None:
        """!@brief 注册状态及其处理函数

        @param name    状态名称
        @param handler 处理函数，签名为 handler(*args) -> bool
                       返回False表示退出主循环
        """
        self._states[name] = handler

    def add_transition(self, from_state: str, to_state: str,
                       condition: Optional[Callable] = None) -> None:
        """!@brief 添加状态转换规则

        @param from_state 源状态
        @param to_state   目标状态
        @param condition  可选的条件函数，返回True时允许转换
        """
        key = (from_state, to_state)
        self._transitions[key] = condition

    def on_enter(self, state: str, callback: Callable) -> None:
        """!@brief 注册状态进入回调

        @param state    状态名称
        @param callback 回调函数 callback(from_state: str)
        """
        if state not in self._on_enter:
            self._on_enter[state] = []
        self._on_enter[state].append(callback)

    def on_exit(self, state: str, callback: Callable) -> None:
        """!@brief 注册状态退出回调

        @param state    状态名称
        @param callback 回调函数 callback(to_state: str)
        """
        if state not in self._on_exit:
            self._on_exit[state] = []
        self._on_exit[state].append(callback)

    def start(self, initial_state: str) -> None:
        """!@brief 设置初始状态"""
        self._current = initial_state
        self._fire_enter(initial_state, None)

    @property
    def current(self) -> Optional[str]:
        """!@brief 当前状态名称"""
        return self._current

    @property
    def previous(self) -> Optional[str]:
        """!@brief 上一个状态名称"""
        return self._previous

    def can_transition(self, to_state: str) -> bool:
        """!@brief 检查是否可以转换到目标状态"""
        if self._current is None:
            return False
        key = (self._current, to_state)
        condition = self._transitions.get(key)
        if condition is not None and not condition():
            return False
        return True

    def transition(self, to_state: str) -> bool:
        """!@brief 尝试转换到目标状态

        @return True表示转换成功
        """
        if self._current is None:
            return False
        key = (self._current, to_state)
        condition = self._transitions.get(key)
        if condition is not None and not condition():
            return False
        old = self._current
        self._fire_exit(old, to_state)
        self._previous = old
        self._current = to_state
        self._fire_enter(to_state, old)
        _logger.debug('状态转换: %s -> %s', old, to_state)
        return True

    def update(self, *args):
        """!@brief 调用当前状态的handler"""
        if self._current and self._current in self._states:
            return self._states[self._current](*args)
        return True

    def _fire_enter(self, state: str, from_state: Optional[str]) -> None:
        for cb in self._on_enter.get(state, []):
            try:
                cb(from_state)
            except Exception as e:
                _logger.error('状态进入回调异常: %s: %s', state, e)

    def _fire_exit(self, state: str, to_state: str) -> None:
        for cb in self._on_exit.get(state, []):
            try:
                cb(to_state)
            except Exception as e:
                _logger.error('状态退出回调异常: %s: %s', state, e)
