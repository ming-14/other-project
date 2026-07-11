"""!
@file render/scene_builder.py
@brief 场景像素构建模块

将光线投射结果写入像素缓冲区：天花板/地板批量填充 + 墙面逐列覆盖。
优化：行颜色缓存(horizon量化)、垂直遮蔽预计算、常量提升、int像素打包。
"""

import math

import config
from config import (CEILING_TOP, CEILING_BOTTOM, FLOOR_TOP, FLOOR_BOTTOM,
                    WALL_NS_COLOR, WALL_EW_COLOR, EXIT_COLOR,
                    FOG_NEAR, FOG_FAR, FOG_GAMMA, MIN_BRIGHTNESS,
                    WALL_SIDE_SHADE, WALL_VERTICAL_SHADE,
                    WALL_STRIPE_PERIOD, WALL_STRIPE_CONTRAST,
                    PLAYER_EYE_HEIGHT,
                    COLOR_QUANTIZE_ENABLED, COLOR_QUANTIZE_BITS)
from render.lighting import Lighting
from core import log_manager

_logger = log_manager.get_logger('render.scene_builder')

_CEL0 = CEILING_TOP[0]
_CEL1 = CEILING_TOP[1]
_CEL2 = CEILING_TOP[2]
_CEL_DR = CEILING_BOTTOM[0] - _CEL0
_CEL_DG = CEILING_BOTTOM[1] - _CEL1
_CEL_DB = CEILING_BOTTOM[2] - _CEL2

_FLR0 = FLOOR_TOP[0]
_FLR1 = FLOOR_TOP[1]
_FLR2 = FLOOR_TOP[2]
_FLR_DR = FLOOR_BOTTOM[0] - _FLR0
_FLR_DG = FLOOR_BOTTOM[1] - _FLR1
_FLR_DB = FLOOR_BOTTOM[2] - _FLR2

_FOG_RANGE_INV = 1.0 / (FOG_FAR - FOG_NEAR)
_FOG_ONE_MINUS_MIN = 1.0 - MIN_BRIGHTNESS
_VERT_A = 1.0 - WALL_VERTICAL_SHADE
_VERT_B = WALL_VERTICAL_SHADE * 4.0
_TWO_PI = 2.0 * math.pi
_HAS_STRIPE = WALL_STRIPE_PERIOD > 0
if _HAS_STRIPE:
    _STRIPE_INV_PERIOD = 1.0 / WALL_STRIPE_PERIOD

_WALL_NS_PACK = (WALL_NS_COLOR[0] << 16) | (WALL_NS_COLOR[1] << 8) | WALL_NS_COLOR[2]
_WALL_EW_PACK = (WALL_EW_COLOR[0] << 16) | (WALL_EW_COLOR[1] << 8) | WALL_EW_COLOR[2]
_EXIT_PACK = (EXIT_COLOR[0] << 16) | (EXIT_COLOR[1] << 8) | EXIT_COLOR[2]


class SceneBuilder:
    """!@brief 场景像素构建器

    将RayCasting结果写入PixelBuffer。天花板/地板按行批量填充，
    墙面逐列覆盖。行颜色按horizon量化缓存。
    """

    def __init__(self, maze, lighting):
        self.maze = maze
        self.lighting = lighting
        self._cached_horizon_key = None
        self._cached_h = None
        self._row_colors = None

    def _compute_row_colors(self, h, horizon, qtab):
        eye_scale = PLAYER_EYE_HEIGHT * h
        floor_denom = h - horizon
        row_colors = [0] * h
        for y in range(h):
            if y < horizon:
                t = y / horizon if horizon > 0 else 0
                br = _CEL0 + _CEL_DR * t
                bg = _CEL1 + _CEL_DG * t
                bb = _CEL2 + _CEL_DB * t
                dy = horizon - y
            else:
                t = (y - horizon) / floor_denom if floor_denom > 0 else 0
                br = _FLR0 + _FLR_DR * t
                bg = _FLR1 + _FLR_DG * t
                bb = _FLR2 + _FLR_DB * t
                dy = y - horizon
            if dy > 0.5:
                dist = eye_scale / dy
                if dist <= FOG_NEAR:
                    fog = 1.0
                elif dist >= FOG_FAR:
                    fog = MIN_BRIGHTNESS
                else:
                    tt = (dist - FOG_NEAR) * _FOG_RANGE_INV
                    fog = 1.0 - (tt ** FOG_GAMMA) * _FOG_ONE_MINUS_MIN
                cr = int(br * fog)
                cg = int(bg * fog)
                cb = int(bb * fog)
            else:
                cr = int(br)
                cg = int(bg)
                cb = int(bb)
            row_colors[y] = (qtab[cr] << 16) | (qtab[cg] << 8) | qtab[cb]
        return row_colors

    def build(self, buffer, hits, player, camera=None):
        w = buffer.width
        h = buffer.pixel_height
        pitch = camera.effective_pitch if camera else player.pitch
        horizon = h / 2.0 + pitch * (h / 2.0)
        horizon = max(1.0, min(h - 1.0, horizon))

        qtab = self.lighting._qtab

        horizon_key = int(horizon)
        if horizon_key == self._cached_horizon_key and h == self._cached_h:
            row_colors = self._row_colors
        else:
            row_colors = self._compute_row_colors(h, horizon, qtab)
            self._cached_horizon_key = horizon_key
            self._cached_h = h
            self._row_colors = row_colors

        data = buffer.data
        for y in range(h):
            data[y][:] = [row_colors[y]] * w

        for col, hit in enumerate(hits):
            perp_dist = hit.distance
            line_height = h / perp_dist
            draw_start = horizon - line_height * 0.5
            draw_end = horizon + line_height * 0.5
            start_i = max(0, int(draw_start))
            end_i = min(h, int(draw_end))
            wall_span = max(1, end_i - start_i)

            if hit.wall_type == 2:
                br0, br1, br2 = EXIT_COLOR
            elif hit.side == 0:
                br0, br1, br2 = WALL_NS_COLOR
            else:
                br0, br1, br2 = WALL_EW_COLOR

            if perp_dist <= FOG_NEAR:
                fog = 1.0
            elif perp_dist >= FOG_FAR:
                fog = MIN_BRIGHTNESS
            else:
                tt = (perp_dist - FOG_NEAR) * _FOG_RANGE_INV
                fog = 1.0 - (tt ** FOG_GAMMA) * _FOG_ONE_MINUS_MIN

            side_shade = 1.0 if hit.side == 0 else WALL_SIDE_SHADE

            if _HAS_STRIPE:
                phase = hit.wall_x * _STRIPE_INV_PERIOD
                stripe = 1.0 - WALL_STRIPE_CONTRAST * (
                    0.5 - 0.5 * math.cos(phase * _TWO_PI))
            else:
                stripe = 1.0

            col_brightness = fog * side_shade * stripe
            inv_span = 1.0 / wall_span

            for y in range(start_i, end_i):
                t = (y - start_i) * inv_span
                vert_shade = _VERT_A + _VERT_B * t * (1.0 - t)
                b = col_brightness * vert_shade
                data[y][col] = (qtab[int(br0 * b)] << 16) | (qtab[int(br1 * b)] << 8) | qtab[int(br2 * b)]
