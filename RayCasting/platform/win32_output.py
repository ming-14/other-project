"""!
@file platform/win32_output.py
@brief Win32直接缓冲区输出实现

通过WriteConsoleOutput API直接写入控制台屏幕缓冲区，
绕过ANSI序列解析瓶颈。仅传统conhost控制台支持。
"""

import ctypes
from ctypes import wintypes
import logging
import struct

import config
from platform.base import PlatformOutput
from core import log_manager

_logger = log_manager.get_logger('platform.win32_output')


class _COORD(ctypes.Structure):
    _fields_ = [('X', wintypes.SHORT), ('Y', wintypes.SHORT)]


class _CHAR_INFO(ctypes.Structure):
    _fields_ = [
        ('Char', wintypes.WCHAR),
        ('Attributes', wintypes.WORD),
    ]


class _CONSOLE_SCREEN_BUFFER_INFOEX(ctypes.Structure):
    _fields_ = [
        ('cbSize',               wintypes.ULONG),
        ('dwSize',               _COORD),
        ('dwCursorPosition',     _COORD),
        ('wAttributes',          wintypes.WORD),
        ('srWindow',             wintypes.SMALL_RECT),
        ('dwMaximumWindowSize',  _COORD),
        ('wPopupAttributes',     wintypes.WORD),
        ('bFullscreenSupported', wintypes.BOOL),
        ('ColorTable',           wintypes.DWORD * 16),
    ]


_kernel32 = ctypes.windll.kernel32
_kernel32.GetStdHandle.argtypes = [wintypes.DWORD]
_kernel32.GetStdHandle.restype = wintypes.HANDLE
_kernel32.GetConsoleWindow.argtypes = []
_kernel32.GetConsoleWindow.restype = wintypes.HWND
_kernel32.WriteConsoleOutputW.argtypes = [
    wintypes.HANDLE, ctypes.POINTER(_CHAR_INFO),
    _COORD, _COORD,
    ctypes.POINTER(wintypes.SMALL_RECT)]
_kernel32.WriteConsoleOutputW.restype = wintypes.BOOL
_kernel32.GetConsoleScreenBufferInfoEx.argtypes = [
    wintypes.HANDLE, ctypes.POINTER(_CONSOLE_SCREEN_BUFFER_INFOEX)]
_kernel32.GetConsoleScreenBufferInfoEx.restype = wintypes.BOOL
_kernel32.SetConsoleScreenBufferInfoEx.argtypes = [
    wintypes.HANDLE, ctypes.POINTER(_CONSOLE_SCREEN_BUFFER_INFOEX)]
_kernel32.SetConsoleScreenBufferInfoEx.restype = wintypes.BOOL
_kernel32.GetLastError.argtypes = []
_kernel32.GetLastError.restype = wintypes.DWORD
_kernel32.SetConsoleWindowInfo.argtypes = [
    wintypes.HANDLE, wintypes.BOOL,
    ctypes.POINTER(wintypes.SMALL_RECT)]
_kernel32.SetConsoleWindowInfo.restype = wintypes.BOOL
_kernel32.SetConsoleScreenBufferSize.argtypes = [
    wintypes.HANDLE, _COORD]
_kernel32.SetConsoleScreenBufferSize.restype = wintypes.BOOL

STD_OUTPUT_HANDLE = 0xFFFFFFF5

_SCENE_PALETTE = [
    (0,   0,   0  ),
    (8,   8,   32 ),
    (24,  24,  48 ),
    (32,  32,  64 ),
    (40,  32,  24 ),
    (52,  44,  36 ),
    (64,  56,  48 ),
    (48,  48,  72 ),
    (72,  72,  96 ),
    (96,  96,  128),
    (144, 144, 168),
    (56,  200, 88 ),
    (88,  88,  120),
    (16,  16,  24 ),
    (240, 240, 80 ),
    (200, 200, 200),
]


_rgb_cache = {}

_LUT_R_STEPS = 6
_LUT_G_STEPS = 6
_LUT_B_STEPS = 6
_LUT_R_SCALE = _LUT_R_STEPS - 1
_LUT_G_SCALE = _LUT_G_STEPS - 1
_LUT_B_SCALE = _LUT_B_STEPS - 1

_rgb_lut = [0] * (_LUT_R_STEPS * _LUT_G_STEPS * _LUT_B_STEPS)
_lut_built = False


def _build_rgb_lut():
    """!@brief 预计算6x6x6量化RGB→调色板索引查找表"""
    global _lut_built
    for ri in range(_LUT_R_STEPS):
        r = int(ri * 255.0 / _LUT_R_SCALE + 0.5)
        for gi in range(_LUT_G_STEPS):
            g = int(gi * 255.0 / _LUT_G_SCALE + 0.5)
            for bi in range(_LUT_B_STEPS):
                b = int(bi * 255.0 / _LUT_B_SCALE + 0.5)
                best, best_d = 0, 1 << 30
                for k, (pr, pg, pb) in enumerate(_SCENE_PALETTE):
                    dr = r - pr
                    dg = g - pg
                    db = b - pb
                    d = dr * dr + dg * dg + db * db
                    if d < best_d:
                        best, best_d = k, d
                _rgb_lut[ri * _LUT_G_STEPS * _LUT_B_STEPS + gi * _LUT_B_STEPS + bi] = best
    _lut_built = True


def _rgb_to_attr(r, g, b):
    key = (r, g, b)
    cached = _rgb_cache.get(key)
    if cached is not None:
        return cached
    if not _lut_built:
        _build_rgb_lut()
    ri = (r * _LUT_R_SCALE + 127) // 255
    gi = (g * _LUT_G_SCALE + 127) // 255
    bi = (b * _LUT_B_SCALE + 127) // 255
    ri = max(0, min(_LUT_R_SCALE, ri))
    gi = max(0, min(_LUT_G_SCALE, gi))
    bi = max(0, min(_LUT_B_SCALE, bi))
    lut_idx = ri * _LUT_G_STEPS * _LUT_B_STEPS + gi * _LUT_B_STEPS + bi
    result = _rgb_lut[lut_idx]
    if len(_rgb_cache) < 16384:
        _rgb_cache[key] = result
    return result


class Win32ConsoleOutput(PlatformOutput):
    """!@brief Win32直接缓冲区输出实现"""

    def __init__(self):
        self._available = False
        self._handle = None
        self._saved_palette = None
        self._detect()
        if self._available:
            self._fix_viewport()
            self._init_palette()

    def _detect(self):
        if not config.BYPASS_ANSI_ENABLED:
            self._available = False
            return
        if config.COLOR_QUANTIZE_ENABLED:
            self._available = False
            return
        hwnd = _kernel32.GetConsoleWindow()
        if not hwnd:
            self._available = False
            return
        self._handle = _kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
        self._available = True

    def available(self):
        return self._available

    def _init_palette(self):
        try:
            info = _CONSOLE_SCREEN_BUFFER_INFOEX()
            info.cbSize = ctypes.sizeof(_CONSOLE_SCREEN_BUFFER_INFOEX)
            ok = _kernel32.GetConsoleScreenBufferInfoEx(
                self._handle, ctypes.byref(info))
            if not ok:
                _logger.error('_init_palette: GetConsoleScreenBufferInfoEx失败, 错误码=%d',
                              _kernel32.GetLastError())
                return False
            self._saved_palette = list(info.ColorTable[:16])
            for i, (r, g, b) in enumerate(_SCENE_PALETTE):
                info.ColorTable[i] = r | (g << 8) | (b << 16)
            ok = _kernel32.SetConsoleScreenBufferInfoEx(
                self._handle, ctypes.byref(info))
            if not ok:
                self._saved_palette = None
                _logger.error('_init_palette: SetConsoleScreenBufferInfoEx失败, 错误码=%d',
                              _kernel32.GetLastError())
                return False
            return True
        except Exception as e:
            self._saved_palette = None
            _logger.error('_init_palette: 异常 %s', e)
            return False

    def _restore_palette(self):
        if self._saved_palette is None or self._handle is None:
            return
        try:
            info = _CONSOLE_SCREEN_BUFFER_INFOEX()
            info.cbSize = ctypes.sizeof(_CONSOLE_SCREEN_BUFFER_INFOEX)
            ok = _kernel32.GetConsoleScreenBufferInfoEx(
                self._handle, ctypes.byref(info))
            if ok:
                info.ColorTable = (wintypes.DWORD * 16)(*self._saved_palette)
                _kernel32.SetConsoleScreenBufferInfoEx(
                    self._handle, ctypes.byref(info))
        except Exception:
            pass

    def _fix_viewport(self):
        """!@brief 将屏幕缓冲区缩为窗口大小，锁定视口到(0,0)

        cmd默认缓冲区高度(9001)远大于窗口(30)，ANSI序列会滚动视口，
        导致WriteConsoleOutputW写到(0,0)时内容在视口上方不可见。
        将缓冲区缩为窗口大小后，视口无法滚动，始终对齐(0,0)。
        """
        try:
            info = _CONSOLE_SCREEN_BUFFER_INFOEX()
            info.cbSize = ctypes.sizeof(_CONSOLE_SCREEN_BUFFER_INFOEX)
            if not _kernel32.GetConsoleScreenBufferInfoEx(
                    self._handle, ctypes.byref(info)):
                return
            win_w = info.srWindow.Right - info.srWindow.Left + 1
            win_h = info.srWindow.Bottom - info.srWindow.Top + 1
            viewport = wintypes.SMALL_RECT(0, 0, win_w - 1, win_h - 1)
            _kernel32.SetConsoleWindowInfo(self._handle, True,
                                           ctypes.byref(viewport))
            _kernel32.SetConsoleScreenBufferSize(
                self._handle, _COORD(win_w, win_h))
            _kernel32.SetConsoleWindowInfo(self._handle, True,
                                           ctypes.byref(viewport))
        except Exception:
            pass

    def write_frame(self, buffer, width, height, hud_text=''):
        if not self._available:
            return
        self._fix_viewport()
        cell_count = width * height
        _rgb_to_attr_local = _rgb_to_attr
        chars = [0x2580] * cell_count
        attrs = [0] * cell_count
        idx = 0
        for row in range(height):
            top_y = row * 2
            bot_y = row * 2 + 1
            row_top = buffer[top_y]
            row_bot = buffer[bot_y]
            for col in range(width):
                top = row_top[col]
                bot = row_bot[col]
                fg = _rgb_to_attr_local((top >> 16) & 0xFF, (top >> 8) & 0xFF, top & 0xFF)
                bg = _rgb_to_attr_local((bot >> 16) & 0xFF, (bot >> 8) & 0xFF, bot & 0xFF)
                attrs[idx] = (bg << 4) | fg
                idx += 1

        if hud_text and height > 0:
            row_offset = (height - 1) * width
            for col, ch in enumerate(hud_text):
                if col >= width:
                    break
                ci = row_offset + col
                chars[ci] = ord(ch)
                attrs[ci] = 0x0F

        char_buf = (_CHAR_INFO * cell_count)()
        pack = struct.pack
        raw_data = bytearray(cell_count * 4)
        offset = 0
        for i in range(cell_count):
            c = chars[i]
            a = attrs[i]
            raw_data[offset:offset + 4] = pack('<HH', c, a)
            offset += 4
        raw = (ctypes.c_ubyte * (cell_count * 4)).from_buffer(raw_data)
        ctypes.memmove(char_buf, raw, cell_count * 4)

        region = wintypes.SMALL_RECT(0, 0, width - 1, height - 1)
        size = _COORD(width, height)
        coord = _COORD(0, 0)
        ok = _kernel32.WriteConsoleOutputW(
            self._handle, char_buf, size, coord, ctypes.byref(region))
        if not ok:
            err = _kernel32.GetLastError()
            _logger.error('write_frame: WriteConsoleOutputW失败, 错误码=%d, 回退ANSI', err)
            self._available = False
            import sys
            sys.stderr.write('WriteConsoleOutputW失败, 错误码: %d, 已回退ANSI\n' % err)

    def write_message(self, message):
        import sys
        sys.stdout.write('\033[H' + message)
        sys.stdout.flush()
        self._fix_viewport()

    def shutdown(self):
        self._restore_palette()
