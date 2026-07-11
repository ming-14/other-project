"""!
@file render/sprite_renderer.py
@brief 精灵渲染器

在3D场景中渲染Billboard精灵，使用z-buffer与墙壁正确遮挡。
集成到渲染管线中作为渲染层使用。
"""

import math
from typing import Optional

from world.sprite import SpriteComponent
from core import log_manager

_logger = log_manager.get_logger('render.sprite_renderer')


class _SpriteEntry:
    __slots__ = ('entity', 'transform_y', 'transform_x', 'distance')

    def __init__(self, entity, transform_y, transform_x, distance):
        self.entity = entity
        self.transform_y = transform_y
        self.transform_x = transform_x
        self.distance = distance


class SpriteRenderer:
    """!@brief 精灵渲染器

    在3D场景中渲染Billboard精灵。
    使用z-buffer与墙壁正确遮挡，画家算法排序。
    """

    def __init__(self, entity_manager):
        self._entity_manager = entity_manager

    def on_render(self, context: dict) -> None:
        buffer = context['buffer']
        hits = context.get('hits', [])
        player = context['player']

        z_buffer = [hit.distance for hit in hits] if hits else None

        visible = self._collect_visible(player, buffer)
        visible.sort(key=lambda e: e.distance, reverse=True)

        for entry in visible:
            self._render_sprite(buffer, entry, z_buffer, player,
                                buffer.width, buffer.pixel_height)

    def _collect_visible(self, player, buffer) -> list:
        px, py = player.x, player.y
        dir_x, dir_y = player.dir_vector
        plane_x, plane_y = player.plane_vector

        det = plane_x * dir_y - dir_x * plane_y
        if abs(det) < 1e-9:
            return []
        inv_det = 1.0 / det

        entities = self._entity_manager.query() \
            .with_component('SpriteComponent') \
            .execute()

        visible = []
        for entity in entities:
            sprite_comp = entity.get_component('SpriteComponent')
            if not sprite_comp or not sprite_comp.current_frame:
                continue

            dx = entity.x - px
            dy = entity.y - py
            distance = math.sqrt(dx * dx + dy * dy)

            if distance > sprite_comp.visible_distance or distance < 0.2:
                continue

            transform_x = inv_det * (dir_y * dx - dir_x * dy)
            transform_y = inv_det * (-plane_y * dx + plane_x * dy)

            if transform_y <= 0.1:
                continue

            screen_x = int((buffer.width / 2) * (1 + transform_x / transform_y))
            sprite_screen_width = abs(int(buffer.width / transform_y))
            half_w = sprite_screen_width // 2
            if screen_x + half_w < 0 or screen_x - half_w >= buffer.width:
                continue

            visible.append(_SpriteEntry(entity, transform_y, transform_x, distance))

        return visible

    def _render_sprite(self, buffer, entry, z_buffer, player,
                       screen_width, screen_height) -> None:
        entity = entry.entity
        sprite_comp = entity.get_component('SpriteComponent')
        frame = sprite_comp.current_frame

        transform_y = entry.transform_y
        transform_x = entry.transform_x

        sprite_height = abs(int(screen_height / transform_y)) * sprite_comp.scale
        aspect = frame.width / frame.height if frame.height > 0 else 1.0
        sprite_width = abs(int(sprite_height * aspect))

        v_offset = sprite_comp.vertical_offset + sprite_comp.current_bob_offset
        horizon = screen_height / 2.0 + player.pitch * (screen_height / 2.0)
        v_offset_pixels = int(v_offset * sprite_height)

        draw_start_y = int(horizon - sprite_height / 2 - v_offset_pixels)
        draw_start_x = int((screen_width / 2) * (1 + transform_x / transform_y)
                           - sprite_width / 2)

        y_start = max(0, draw_start_y)
        y_end = min(screen_height, draw_start_y + int(sprite_height))
        x_start = max(0, draw_start_x)
        x_end = min(screen_width, draw_start_x + int(sprite_width))

        inv_sprite_h = 1.0 / sprite_height if sprite_height > 0 else 0
        inv_sprite_w = 1.0 / sprite_width if sprite_width > 0 else 0

        for y in range(y_start, y_end):
            tex_y = int((y - draw_start_y) * inv_sprite_h * frame.height)
            if tex_y < 0 or tex_y >= frame.height:
                continue
            row = frame.pixels[tex_y]

            for x in range(x_start, x_end):
                if z_buffer and x < len(z_buffer) and transform_y >= z_buffer[x]:
                    continue

                tex_x = int((x - draw_start_x) * inv_sprite_w * frame.width)
                if tex_x < 0 or tex_x >= frame.width:
                    continue

                pixel = row[tex_x]
                if pixel >= 0:
                    buffer.data[y][x] = pixel
