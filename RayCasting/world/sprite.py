"""!
@file world/sprite.py
@brief 精灵系统

定义精灵帧、精灵动画、精灵组件，
支持在3D场景中渲染Billboard精灵。
"""

import math
from typing import Callable, Optional

from world.entity import Component, Entity
from core import log_manager

_logger = log_manager.get_logger('world.sprite')


class SpriteFrame:
    """!@brief 单帧精灵数据

    像素以int打包存储(r<<16|g<<8|b)，-1表示透明。
    """

    __slots__ = ('width', 'height', 'pixels', 'offset_x', 'offset_y')

    def __init__(self, width: int, height: int,
                 pixels: list = None,
                 offset_x: float = 0.0, offset_y: float = 0.0):
        self.width = width
        self.height = height
        self.pixels = pixels or []
        self.offset_x = offset_x
        self.offset_y = offset_y

    @staticmethod
    def from_color(width: int, height: int, color: tuple,
                   shape: str = 'rect') -> 'SpriteFrame':
        packed = (color[0] << 16) | (color[1] << 8) | color[2]
        pixels = []
        hw = width / 2.0
        hh = height / 2.0
        r = min(width, height) / 2.0
        for y in range(height):
            row = []
            for x in range(width):
                if shape == 'rect':
                    row.append(packed)
                elif shape == 'diamond':
                    if abs(x - hw + 0.5) + abs(y - hh + 0.5) <= r:
                        row.append(packed)
                    else:
                        row.append(-1)
                elif shape == 'circle':
                    dx = x - hw + 0.5
                    dy = y - hh + 0.5
                    if dx * dx + dy * dy <= r * r:
                        row.append(packed)
                    else:
                        row.append(-1)
                else:
                    row.append(packed)
            pixels.append(row)
        return SpriteFrame(width, height, pixels)

    @staticmethod
    def from_ascii(art: list, color_map: dict) -> 'SpriteFrame':
        height = len(art)
        width = max(len(row) for row in art) if art else 0
        pixels = []
        for y, row_str in enumerate(art):
            pixel_row = []
            for x, ch in enumerate(row_str):
                if ch in color_map:
                    c = color_map[ch]
                    pixel_row.append((c[0] << 16) | (c[1] << 8) | c[2])
                else:
                    pixel_row.append(-1)
            while len(pixel_row) < width:
                pixel_row.append(-1)
            pixels.append(pixel_row)
        return SpriteFrame(width, height, pixels)


class SpriteAnimation:
    """!@brief 精灵动画 - 帧序列播放"""

    def __init__(self, frames: list, frame_duration: float = 0.1,
                 loop: bool = True):
        self.frames = frames
        self.frame_duration = frame_duration
        self.loop = loop
        self.current_frame = 0
        self.elapsed = 0.0
        self.finished = False

    def update(self, delta_time: float) -> None:
        if self.finished:
            return
        self.elapsed += delta_time
        if self.elapsed >= self.frame_duration:
            self.elapsed -= self.frame_duration
            self.current_frame += 1
            if self.current_frame >= len(self.frames):
                if self.loop:
                    self.current_frame = 0
                else:
                    self.current_frame = len(self.frames) - 1
                    self.finished = True

    @property
    def current(self) -> SpriteFrame:
        return self.frames[self.current_frame]

    def reset(self) -> None:
        self.current_frame = 0
        self.elapsed = 0.0
        self.finished = False


class SpriteComponent(Component):
    """!@brief 精灵组件 - 附加到实体使其在3D场景中可见"""

    def __init__(self, frame: SpriteFrame = None,
                 visible_distance: float = 15.0):
        super().__init__()
        self.frame = frame
        self.animations: dict[str, SpriteAnimation] = {}
        self._current_animation: Optional[str] = None
        self.visible_distance = visible_distance
        self.billboard = True
        self.scale = 1.0
        self.vertical_offset = 0.0
        self.bob_amplitude = 0.0
        self.bob_speed = 0.0
        self._bob_phase = 0.0

    def on_attach(self, entity):
        pass

    def on_detach(self, entity):
        pass

    def on_update(self, entity, delta_time):
        if self._current_animation and self._current_animation in self.animations:
            self.animations[self._current_animation].update(delta_time)
        if self.bob_speed > 0:
            self._bob_phase += self.bob_speed * delta_time

    def add_animation(self, name: str, animation: SpriteAnimation) -> None:
        self.animations[name] = animation

    def play(self, name: str, reset: bool = True) -> None:
        if name in self.animations:
            self._current_animation = name
            if reset:
                self.animations[name].reset()

    def stop_animation(self) -> None:
        self._current_animation = None

    @property
    def current_frame(self) -> Optional[SpriteFrame]:
        if self._current_animation and self._current_animation in self.animations:
            return self.animations[self._current_animation].current
        return self.frame

    @property
    def current_bob_offset(self) -> float:
        if self.bob_amplitude > 0 and self.bob_speed > 0:
            return self.bob_amplitude * math.sin(self._bob_phase)
        return 0.0
