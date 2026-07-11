"""!
@file render/postprocess/base.py
@brief 后处理效果抽象基类

定义可插入渲染管线的后处理效果接口。
"""

from abc import ABC, abstractmethod
from typing import Any


class PostProcessEffect(ABC):
    """!@brief 后处理效果协议

    所有后处理效果必须实现此接口。
    效果在场景构建完成后、输出前执行。
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """!@brief 效果名称"""
        ...

    @property
    def priority(self) -> int:
        """!@brief 优先级，越小越先执行"""
        return 100

    @property
    def enabled(self) -> bool:
        """!@brief 是否启用"""
        return self._enabled

    def __init__(self):
        self._enabled = True

    def enable(self) -> None:
        """!@brief 启用效果"""
        self._enabled = True

    def disable(self) -> None:
        """!@brief 禁用效果"""
        self._enabled = False

    @abstractmethod
    def apply(self, buffer: Any, context: dict) -> None:
        """!@brief 应用后处理效果

        @param buffer  像素缓冲区
        @param context 渲染上下文
        """
        ...


class ScanlineEffect(PostProcessEffect):
    """!@brief 扫描线效果"""

    @property
    def name(self) -> str:
        return 'scanline'

    @property
    def priority(self) -> int:
        return 100

    def __init__(self, intensity: float = 0.15, gap: int = 2):
        super().__init__()
        self.intensity = intensity
        self.gap = gap

    def apply(self, buffer: Any, context: dict) -> None:
        if not self._enabled:
            return
        data = buffer.data
        h = buffer.pixel_height
        w = buffer.width
        darken = int(255 * self.intensity)
        for y in range(0, h, self.gap):
            row = data[y]
            for x in range(w):
                pixel = row[x]
                r = max(0, ((pixel >> 16) & 0xFF) - darken)
                g = max(0, ((pixel >> 8) & 0xFF) - darken)
                b = max(0, (pixel & 0xFF) - darken)
                row[x] = (r << 16) | (g << 8) | b


class VignetteEffect(PostProcessEffect):
    """!@brief 暗角效果"""

    @property
    def name(self) -> str:
        return 'vignette'

    @property
    def priority(self) -> int:
        return 200

    def __init__(self, strength: float = 0.3, radius: float = 0.7):
        super().__init__()
        self.strength = strength
        self.radius = radius

    def apply(self, buffer: Any, context: dict) -> None:
        if not self._enabled:
            return
        data = buffer.data
        h = buffer.pixel_height
        w = buffer.width
        cx = w / 2.0
        cy = h / 2.0
        max_dist = (cx * cx + cy * cy) ** 0.5
        for y in range(h):
            row = data[y]
            dy = (y - cy) / max_dist
            for x in range(w):
                dx = (x - cx) / max_dist
                dist = (dx * dx + dy * dy) ** 0.5
                if dist > self.radius:
                    factor = max(0.0, 1.0 - (dist - self.radius) * self.strength)
                    pixel = row[x]
                    r = int(((pixel >> 16) & 0xFF) * factor)
                    g = int(((pixel >> 8) & 0xFF) * factor)
                    b = int((pixel & 0xFF) * factor)
                    row[x] = (r << 16) | (g << 8) | b
