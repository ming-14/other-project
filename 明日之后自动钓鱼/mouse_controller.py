# -*- coding: utf-8 -*-
"""
@file       mouse_controller.py
@brief      鼠标模拟输入模块
@details    封装 SendInput API，提供移动光标、按下/释放左键等操作。
"""

import ctypes
from ctypes import wintypes

from win32_defs import (
    user32, INPUT, INPUT_MOUSE,
    MOUSEEVENTF_MOVE, MOUSEEVENTF_ABSOLUTE,
    MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP
)


class MouseController:
    @staticmethod
    def send_move_abs(x_abs: int, y_abs: int) -> bool:
        inp = INPUT()
        inp.type = INPUT_MOUSE
        inp.mi.dx = x_abs
        inp.mi.dy = y_abs
        inp.mi.mouseData = 0
        inp.mi.dwFlags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE
        inp.mi.time = 0
        inp.mi.dwExtraInfo = 0
        sent = user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
        return sent == 1

    @staticmethod
    def send_left_down() -> bool:
        inp = INPUT()
        inp.type = INPUT_MOUSE
        inp.mi.dx = 0
        inp.mi.dy = 0
        inp.mi.mouseData = 0
        inp.mi.dwFlags = MOUSEEVENTF_LEFTDOWN
        inp.mi.time = 0
        inp.mi.dwExtraInfo = 0
        sent = user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
        return sent == 1

    @staticmethod
    def send_left_up() -> bool:
        inp = INPUT()
        inp.type = INPUT_MOUSE
        inp.mi.dx = 0
        inp.mi.dy = 0
        inp.mi.mouseData = 0
        inp.mi.dwFlags = MOUSEEVENTF_LEFTUP
        inp.mi.time = 0
        inp.mi.dwExtraInfo = 0
        sent = user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
        return sent == 1

    @staticmethod
    def click_at_abs(x_abs: int, y_abs: int, press: bool) -> bool:
        if not MouseController.send_move_abs(x_abs, y_abs):
            return False
        if press:
            return MouseController.send_left_down()
        else:
            return MouseController.send_left_up()
