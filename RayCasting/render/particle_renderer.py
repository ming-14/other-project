"""!
@file render/particle_renderer.py
@brief 粒子渲染层

在3D场景中渲染粒子效果。
"""

import math
from typing import Optional

from world.particle import ParticleEmitter
from core import log_manager

_logger = log_manager.get_logger('render.particle_renderer')


class ParticleRenderLayer:
    """!@brief 粒子渲染层"""

    def __init__(self, emitters: list = None, player=None):
        self._emitters = emitters or []
        self._player = player

    def add_emitter(self, emitter: ParticleEmitter) -> None:
        self._emitters.append(emitter)

    def remove_emitter(self, emitter: ParticleEmitter) -> None:
        if emitter in self._emitters:
            self._emitters.remove(emitter)

    def on_render(self, context):
        buffer = context['buffer']
        player = self._player
        if not player:
            return

        dir_x, dir_y = player.dir_vector
        plane_x, plane_y = player.plane_vector
        det = plane_x * dir_y - dir_x * plane_y
        if abs(det) < 1e-9:
            return
        inv_det = 1.0 / det

        for emitter in self._emitters:
            for particle in emitter.particles:
                dx = particle.x - player.x
                dy = particle.y - player.y
                dist_sq = dx * dx + dy * dy
                if dist_sq > 169.0 or dist_sq < 0.09:
                    continue

                transform_x = inv_det * (dir_y * dx - dir_x * dy)
                transform_y = inv_det * (-plane_y * dx + plane_x * dy)
                if transform_y <= 0.1:
                    continue

                screen_x = int((buffer.width / 2) * (1 + transform_x / transform_y))
                screen_y = int(buffer.pixel_height / 2)

                alpha = particle.alpha
                r = int(particle.color[0] * alpha)
                g = int(particle.color[1] * alpha)
                b = int(particle.color[2] * alpha)
                packed = (r << 16) | (g << 8) | b

                size = max(1, int(particle.size / transform_y))
                for dy_off in range(-size, size + 1):
                    for dx_off in range(-size, size + 1):
                        sx = screen_x + dx_off
                        sy = screen_y + dy_off
                        if 0 <= sx < buffer.width and 0 <= sy < buffer.pixel_height:
                            buffer.data[sy][sx] = packed
