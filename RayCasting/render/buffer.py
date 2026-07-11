"""!
@file render/buffer.py
@brief 像素缓冲区管理模块

维护虚拟像素缓冲区的创建、尺寸调整与读写操作。
像素以int打包存储: r<<16 | g<<8 | b，消除tuple分配开销。
"""

import shutil

import config
from core import log_manager

_logger = log_manager.get_logger('render.buffer')


def _pack(r, g, b):
    return (r << 16) | (g << 8) | b


def _unpack(pixel):
    return ((pixel >> 16) & 0xFF, (pixel >> 8) & 0xFF, pixel & 0xFF)


class PixelBuffer:
    """!@brief 像素缓冲区

    维护虚拟像素二维数组，每个元素为int打包像素(r<<16|g<<8|b)。
    虚拟像素高度=终端行数*2（半块字符实现2倍纵向分辨率）。
    """

    __slots__ = ('width', 'height', 'pixel_height', 'data')

    def __init__(self, width=80, height=24):
        self.width = width
        self.height = height
        self.pixel_height = height * 2
        self.data = None
        self._init()

    def _init(self):
        self.data = [[0] * self.width for _ in range(self.pixel_height)]

    def resize(self):
        size = shutil.get_terminal_size((80, 24))
        new_w, new_h = size.columns, size.lines
        if new_w != self.width or new_h != self.height:
            self.width = max(new_w, 20)
            self.height = max(new_h, 10)
            self.pixel_height = self.height * 2
            self._init()
            return True
        return False

    def fill_row(self, y, color):
        self.data[y][:] = [color] * self.width

    def set_pixel(self, x, y, color):
        ix, iy = int(x), int(y)
        if 0 <= ix < self.width and 0 <= iy < self.pixel_height:
            self.data[iy][ix] = color

    def __getitem__(self, y):
        return self.data[y]

    def __setitem__(self, y, value):
        self.data[y] = value
