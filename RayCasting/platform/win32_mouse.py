"""!
@file platform/win32_mouse.py
@brief Win32鼠标输入实现

通过Win32 API实现FPS风格的鼠标视角控制。
"""

import ctypes
from ctypes import wintypes

import config
from input.base import MouseInput
from core import log_manager

_logger = log_manager.get_logger('platform.win32_mouse')


class Win32MouseInput(MouseInput):
    """!@brief Win32鼠标输入实现"""

    def __init__(self):
        self._user32 = ctypes.windll.user32
        self._kernel32 = ctypes.windll.kernel32
        self._enabled = False
        self._cursor_hidden = False
        self._last_button = False
        self._center = (0, 0)
        self._setup_prototypes()
        self._disable_console_mouse_input()

    def _setup_prototypes(self):
        u = self._user32
        u.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
        u.GetCursorPos.restype = wintypes.BOOL
        u.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
        u.SetCursorPos.restype = wintypes.BOOL
        u.ShowCursor.argtypes = [wintypes.BOOL]
        u.ShowCursor.restype = ctypes.c_int
        u.GetAsyncKeyState.argtypes = [ctypes.c_int]
        u.GetAsyncKeyState.restype = ctypes.c_short
        u.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        u.GetWindowRect.restype = wintypes.BOOL
        u.GetForegroundWindow.argtypes = []
        u.GetForegroundWindow.restype = wintypes.HWND
        self._kernel32.GetStdHandle.argtypes = [ctypes.c_void_p]
        self._kernel32.GetConsoleMode.argtypes = [wintypes.HANDLE,
                                                   ctypes.POINTER(wintypes.DWORD)]
        self._kernel32.SetConsoleMode.argtypes = [wintypes.HANDLE, wintypes.DWORD]

    def _disable_console_mouse_input(self):
        try:
            STD_INPUT_HANDLE = -10
            ENABLE_MOUSE_INPUT = 0x0010
            ENABLE_QUICK_EDIT_MODE = 0x0040
            ENABLE_EXTENDED_FLAGS = 0x0080
            handle = self._kernel32.GetStdHandle(STD_INPUT_HANDLE)
            mode = wintypes.DWORD()
            if self._kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                new_mode = (mode.value & ~ENABLE_MOUSE_INPUT
                            & ~ENABLE_QUICK_EDIT_MODE) | ENABLE_EXTENDED_FLAGS
                self._kernel32.SetConsoleMode(handle, new_mode)
        except Exception:
            pass

    def _is_key_down(self, vk):
        state = self._user32.GetAsyncKeyState(vk)
        return (state & 0x8000) != 0

    def _hide_cursor(self):
        if not self._cursor_hidden:
            self._user32.ShowCursor(False)
            self._cursor_hidden = True

    def _show_cursor(self):
        if self._cursor_hidden:
            self._user32.ShowCursor(True)
            self._cursor_hidden = False

    def _compute_center(self):
        hwnd = self._user32.GetForegroundWindow()
        if hwnd:
            rect = wintypes.RECT()
            if self._user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                w = rect.right - rect.left
                h = rect.bottom - rect.top
                if w > 100 and h > 100:
                    return ((rect.left + rect.right) // 2,
                            (rect.top + rect.bottom) // 2)
        point = wintypes.POINT()
        self._user32.GetCursorPos(ctypes.byref(point))
        return (point.x, point.y)

    def enable(self):
        self._enabled = True
        self._center = self._compute_center()
        self._user32.SetCursorPos(self._center[0], self._center[1])
        self._hide_cursor()

    def disable(self):
        self._enabled = False
        self._show_cursor()

    def toggle(self):
        if self._enabled:
            self.disable()
        else:
            self.enable()

    @property
    def enabled(self):
        return self._enabled

    def poll_click(self):
        button_down = self._is_key_down(config.VK_LBUTTON)
        clicked = button_down and not self._last_button
        self._last_button = button_down
        return clicked

    def update_motion(self):
        if not self._enabled:
            return 0.0, 0.0

        point = wintypes.POINT()
        if not self._user32.GetCursorPos(ctypes.byref(point)):
            return 0.0, 0.0

        dx = point.x - self._center[0]
        dy = point.y - self._center[1]
        self._user32.SetCursorPos(self._center[0], self._center[1])

        rotate_delta = dx * config.MOUSE_SENSITIVITY
        pitch_delta = -dy * config.MOUSE_PITCH_SENSITIVITY
        return rotate_delta, pitch_delta

    def shutdown(self):
        self.disable()
