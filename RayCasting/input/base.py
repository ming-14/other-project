"""!
@file input/base.py
@brief 输入系统抽象基类

定义键盘输入与鼠标输入的抽象接口，平台实现类必须继承并实现所有方法。
支持动作绑定回调。
"""

from abc import ABC, abstractmethod
from typing import Callable, Optional
from input.action_map import ActionMap


class InputSystem(ABC):
    """!@brief 键盘输入系统抽象基类"""

    def __init__(self):
        self._action_map = ActionMap()
        self._on_key_down_callbacks: list[Callable[[str], None]] = []
        self._on_key_up_callbacks: list[Callable[[str], None]] = []

    @abstractmethod
    def poll(self) -> dict:
        """!@brief 状态式查询当前帧所有控制键的按下状态

        @return dict，各动作的布尔按下状态
        """
        ...

    @abstractmethod
    def wait_key(self) -> bool:
        """!@brief 阻塞等待任意按键

        @return True表示ESC（退出），False表示其它任意键
        """
        ...

    def bind_action(self, action: str, callback: Callable[[bool], None]) -> None:
        """!@brief 绑定动作回调

        @param action   动作名称
        @param callback 回调 handler(pressed: bool)
        """
        self._action_map.bind(action, callback)

    def unbind_action(self, action: str) -> None:
        """!@brief 解绑动作回调"""
        self._action_map.unbind(action)

    def process_actions(self, actions: dict) -> None:
        """!@brief 处理动作并触发绑定回调"""
        self._action_map.process_actions(actions)

    @property
    def action_map(self) -> ActionMap:
        """!@brief 获取动作映射"""
        return self._action_map

    def on_key_down(self, callback: Callable[[str], None]) -> None:
        """!@brief 注册按键按下回调"""
        self._on_key_down_callbacks.append(callback)

    def on_key_up(self, callback: Callable[[str], None]) -> None:
        """!@brief 注册按键释放回调"""
        self._on_key_up_callbacks.append(callback)


class MouseInput(ABC):
    """!@brief 鼠标输入抽象基类"""

    def __init__(self):
        self._on_click_callbacks: list[Callable] = []
        self._on_motion_callbacks: list[Callable[[float, float], None]] = []

    @abstractmethod
    def poll_click(self) -> bool:
        """!@brief 检测鼠标左键点击（上升沿）

        @return True表示本帧发生一次左键点击
        """
        ...

    @abstractmethod
    def update_motion(self) -> tuple:
        """!@brief 采集鼠标位移，返回视角增量

        @return (rotate_delta, pitch_delta)
        """
        ...

    @abstractmethod
    def enable(self) -> None:
        """!@brief 启用鼠标视角"""
        ...

    @abstractmethod
    def disable(self) -> None:
        """!@brief 禁用鼠标视角"""
        ...

    @abstractmethod
    def toggle(self) -> None:
        """!@brief 切换鼠标锁定状态"""
        ...

    @property
    @abstractmethod
    def enabled(self) -> bool:
        """!@brief 鼠标锁定状态"""
        ...

    @abstractmethod
    def shutdown(self) -> None:
        """!@brief 关闭控制器，恢复鼠标指针"""
        ...

    def on_click(self, callback: Callable) -> None:
        """!@brief 注册点击回调"""
        self._on_click_callbacks.append(callback)

    def on_motion(self, callback: Callable[[float, float], None]) -> None:
        """!@brief 注册鼠标移动回调"""
        self._on_motion_callbacks.append(callback)
