"""!
@file platform/base.py
@brief 平台输出抽象基类

定义控制台输出的抽象接口，平台实现类必须继承并实现所有方法。
支持输出前/后回调。
"""

from abc import ABC, abstractmethod
from typing import Callable


class PlatformOutput(ABC):
    """!@brief 控制台输出抽象基类"""

    def __init__(self):
        self._pre_write_callbacks: list[Callable] = []
        self._post_write_callbacks: list[Callable] = []

    @abstractmethod
    def available(self) -> bool:
        """!@brief 当前输出器是否可用

        @return True表示可用
        """
        ...

    @abstractmethod
    def write_frame(self, buffer, width, height, hud_text=''):
        """!@brief 将渲染缓冲区写入控制台

        @param buffer   像素缓冲区
        @param width    终端列数
        @param height   终端行数
        @param hud_text HUD文本
        """
        ...

    @abstractmethod
    def write_message(self, message):
        """!@brief 输出居中提示信息

        @param message 提示文本
        """
        ...

    @abstractmethod
    def shutdown(self):
        """!@brief 退出前清理（恢复调色板等）"""
        ...

    def on_pre_write(self, callback: Callable) -> None:
        """!@brief 注册输出前回调"""
        self._pre_write_callbacks.append(callback)

    def on_post_write(self, callback: Callable) -> None:
        """!@brief 注册输出后回调"""
        self._post_write_callbacks.append(callback)

    def _fire_pre_write(self) -> None:
        for cb in self._pre_write_callbacks:
            try:
                cb()
            except Exception:
                pass

    def _fire_post_write(self) -> None:
        for cb in self._post_write_callbacks:
            try:
                cb()
            except Exception:
                pass

    @staticmethod
    def create():
        """!@brief 工厂方法：根据环境自动选择最优输出实现

        @return PlatformOutput实例
        """
        from platform.win32_output import Win32ConsoleOutput
        from platform.ansi_output import ANSIOutput

        win32 = Win32ConsoleOutput()
        if win32.available():
            return win32
        return ANSIOutput()
