"""!
@file world/particle.py
@brief 粒子系统

提供简易粒子发射器，用于视觉效果（金币闪光、碰撞火花等）。
"""

import math
import random
from typing import Callable, Optional

from core import log_manager

_logger = log_manager.get_logger('world.particle')


class Particle:
    """!@brief 单个粒子"""

    __slots__ = ('x', 'y', 'vx', 'vy', 'life', 'max_life',
                 'color', 'size', 'gravity')

    def __init__(self, x, y, vx, vy, life, color, size=1, gravity=0):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.life = life
        self.max_life = life
        self.color = color
        self.size = size
        self.gravity = gravity

    def update(self, delta_time):
        self.x += self.vx * delta_time
        self.y += self.vy * delta_time
        self.vy += self.gravity * delta_time
        self.life -= delta_time

    @property
    def alive(self):
        return self.life > 0

    @property
    def alpha(self):
        return max(0.0, self.life / self.max_life)


class ParticleEmitter:
    """!@brief 粒子发射器"""

    def __init__(self, x: float, y: float, config: dict = None):
        self.x = x
        self.y = y
        self.active = True
        self._particles: list[Particle] = []
        self._config = config or {}
        self._emit_timer = 0.0

        self.rate = self._config.get('rate', 10)
        self.particle_life = self._config.get('life', 1.0)
        self.speed = self._config.get('speed', 2.0)
        self.speed_variance = self._config.get('speed_var', 1.0)
        self.angle = self._config.get('angle', 0.0)
        self.angle_spread = self._config.get('angle_spread', math.pi * 2)
        self.color = self._config.get('color', (255, 200, 50))
        self.size = self._config.get('size', 2)
        self.gravity = self._config.get('gravity', 0.0)
        self.max_particles = self._config.get('max_particles', 50)

    def emit(self, count: int = 1) -> None:
        for _ in range(count):
            if len(self._particles) >= self.max_particles:
                break
            a = self.angle + random.uniform(-self.angle_spread / 2,
                                             self.angle_spread / 2)
            s = self.speed + random.uniform(-self.speed_variance,
                                             self.speed_variance)
            self._particles.append(Particle(
                self.x, self.y,
                math.cos(a) * s, math.sin(a) * s,
                self.particle_life, self.color, self.size, self.gravity
            ))

    def update(self, delta_time: float) -> None:
        if self.active:
            self._emit_timer += delta_time
            interval = 1.0 / self.rate if self.rate > 0 else 1.0
            while self._emit_timer >= interval:
                self._emit_timer -= interval
                self.emit()

        for p in self._particles:
            p.update(delta_time)
        self._particles = [p for p in self._particles if p.alive]

    @property
    def particles(self) -> list:
        return self._particles

    @property
    def particle_count(self) -> int:
        return len(self._particles)

    def clear(self) -> None:
        self._particles.clear()
