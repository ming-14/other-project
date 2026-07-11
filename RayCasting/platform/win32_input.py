"""!
@file platform/win32_input.py
@brief Win32键盘输入实现

使用GetAsyncKeyState进行状态式按键查询，msvcrt阻塞等待按键。
"""

import msvcrt
import ctypes

from input.base import InputSystem
from core import log_manager

_logger = log_manager.get_logger('platform.win32_input')


class Win32InputSystem(InputSystem):
    """!@brief Win32键盘输入实现"""

    _VK_MAP = {
        'forward':      (0x57, 0x26),
        'backward':     (0x53, 0x28),
        'strafe_left':  (0x41,),
        'strafe_right': (0x44,),
        'turn_left':    (0x25,),
        'turn_right':   (0x27,),
        'sprint':       (0x10,),
        'quit':         (0x1B,),
    }

    def __init__(self):
        super().__init__()
        self._user32 = ctypes.windll.user32
        self._user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
        self._user32.GetAsyncKeyState.restype = ctypes.c_short

    def _is_down(self, vk):
        return (self._user32.GetAsyncKeyState(vk) & 0x8000) != 0

    def poll(self):
        actions = {}
        for action, vks in self._VK_MAP.items():
            actions[action] = any(self._is_down(vk) for vk in vks)
        return actions

    def wait_key(self):
        while msvcrt.kbhit():
            msvcrt.getch()
        ch = msvcrt.getch()
        if ch == b'\x1b':
            if msvcrt.kbhit():
                msvcrt.getch()
                msvcrt.getch()
                return False
            return True
        return False
