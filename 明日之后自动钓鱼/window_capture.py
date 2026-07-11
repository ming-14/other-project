# -*- coding: utf-8 -*-
"""
@file       window_capture.py
@brief      窗口捕获与坐标转换模块
@details    负责获取窗口句柄、捕获客户区图像、裁剪标题栏、
            以及将逻辑坐标转换为屏幕绝对坐标。
"""

import ctypes
import time
import sys
import cv2
import numpy as np
import win32gui
from ctypes import wintypes, get_last_error
from typing import Tuple, Optional, List

from win32_defs import user32, gdi32


class WindowCapture:
    CROP_TOP_RATIO = 0.10

    def __init__(self, window_title_substring: str = "ELZ-AN00"):
        self.window_title_substring = window_title_substring
        self.hwnd: Optional[int] = None
        self.client_width: int = 0
        self.client_height: int = 0
        self.crop_top: int = 0
        self._frame_count: int = 0
        self._screen_size: Optional[Tuple[int, int]] = None

    def find_window(self) -> bool:
        def enum_callback(hwnd: int, hwnds: List[int]) -> bool:
            if win32gui.IsWindowVisible(hwnd) and self.window_title_substring in win32gui.GetWindowText(hwnd):
                hwnds.append(hwnd)
            return True

        hwnds: List[int] = []
        win32gui.EnumWindows(enum_callback, hwnds)

        if not hwnds:
            print(f"\u274c 未找到包含\u3010{self.window_title_substring}\u3011的可见窗口")
            return False
        if len(hwnds) > 1:
            print(f"\u26a0\ufe0f 找到 {len(hwnds)} 个匹配窗口，默认使用第一个")
        self.hwnd = hwnds[0]
        return True

    def update_client_size(self) -> bool:
        if not self.hwnd:
            return False
        max_retries = 20
        sleep_interval = 3.0 / max_retries
        for attempt in range(1, max_retries + 1):
            rect = wintypes.RECT()
            if user32.GetClientRect(self.hwnd, ctypes.byref(rect)):
                self.client_width = rect.right - rect.left
                self.client_height = rect.bottom - rect.top
                if self.client_width > 0 and self.client_height > 0:
                    return True
            if attempt < max_retries:
                time.sleep(sleep_interval)
        print(f"\u274c 获取窗口客户区失败，已重试{max_retries}次，程序退出")
        sys.exit(1)

    def capture(self) -> Optional[np.ndarray]:
        if not self.hwnd:
            print("窗口句柄无效，请先调用 find_window()")
            return None

        self._frame_count += 1
        if self._frame_count % 30 == 1 or self.client_width == 0:
            if not self.update_client_size():
                return None

        hdc = mem_dc = bmp = None
        try:
            hdc = user32.GetDC(self.hwnd)
            if not hdc:
                print(f"\u26a0\ufe0f 获取 DC 失败，错误码：{get_last_error()}")
                return None

            mem_dc = gdi32.CreateCompatibleDC(hdc)
            bmp = gdi32.CreateCompatibleBitmap(hdc, self.client_width, self.client_height)
            if not mem_dc or not bmp:
                print(f"\u26a0\ufe0f 创建内存 DC/位图失败，错误码：{get_last_error()}")
                return None

            old_obj = gdi32.SelectObject(mem_dc, bmp)
            user32.PrintWindow(self.hwnd, mem_dc, 0x02)
            gdi32.SelectObject(mem_dc, old_obj)

            buffer_size = self.client_width * self.client_height * 4
            buffer = ctypes.create_string_buffer(buffer_size)
            if gdi32.GetBitmapBits(bmp, buffer_size, buffer) == 0:
                print("\u26a0\ufe0f 读取位图数据失败")
                return None

            img = np.frombuffer(buffer, dtype=np.uint8).reshape(self.client_height, self.client_width, 4)
            img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

            self.crop_top = int(self.client_height * self.CROP_TOP_RATIO)
            img_cropped = img_bgr[self.crop_top:, :]
            return img_cropped

        finally:
            if bmp:
                gdi32.DeleteObject(bmp)
            if mem_dc:
                gdi32.DeleteDC(mem_dc)
            if hdc:
                user32.ReleaseDC(self.hwnd, hdc)

    def client_to_screen(self, client_x: int, client_y: int) -> Optional[Tuple[int, int]]:
        if not self.hwnd:
            return None
        pt = wintypes.POINT(client_x, client_y)
        if not user32.ClientToScreen(self.hwnd, ctypes.byref(pt)):
            print(f"\u26a0\ufe0f ClientToScreen 失败，错误码：{get_last_error()}")
            return None
        return (pt.x, pt.y)

    def get_screen_size(self) -> Tuple[int, int]:
        if self._screen_size is None:
            width = user32.GetSystemMetrics(0)
            height = user32.GetSystemMetrics(1)
            self._screen_size = (width, height)
        return self._screen_size

    def convert_absolute_mouse_coords(self, screen_x: int, screen_y: int) -> Tuple[int, int]:
        scr_w, scr_h = self.get_screen_size()
        abs_x = int((screen_x / scr_w) * 65535.0)
        abs_y = int((screen_y / scr_h) * 65535.0)
        return (abs_x, abs_y)
