"""!
@file render/lighting.py
@brief 光照与雾化计算模块

独立封装距离雾化、侧光、环境光遮蔽、条纹纹理等光照计算逻辑。
支持自定义光照策略与颜色覆盖。
"""

import math
from typing import Callable, Optional, Tuple

import config
from config import (CEILING_TOP, CEILING_BOTTOM, FLOOR_TOP, FLOOR_BOTTOM,
                    WALL_NS_COLOR, WALL_EW_COLOR, EXIT_COLOR,
                    FOG_NEAR, FOG_FAR, FOG_GAMMA, MIN_BRIGHTNESS,
                    WALL_SIDE_SHADE, WALL_VERTICAL_SHADE,
                    WALL_STRIPE_PERIOD, WALL_STRIPE_CONTRAST,
                    PLAYER_EYE_HEIGHT,
                    COLOR_QUANTIZE_ENABLED, COLOR_QUANTIZE_BITS)
from core import log_manager

_logger = log_manager.get_logger('render.lighting')


class Lighting:
    """!@brief 光照计算器

    提供雾化因子、墙面颜色、天花板/地板颜色等查询接口。
    支持自定义颜色覆盖与光照回调。
    """

    def __init__(self):
        if COLOR_QUANTIZE_ENABLED:
            _shift = 8 - COLOR_QUANTIZE_BITS
            self._qtab = bytes((c >> _shift) << _shift for c in range(256))
        else:
            self._qtab = bytes(range(256))
        self._wall_color_overrides: dict[int, Tuple[int, int, int]] = {}
        self._fog_factor_fn: Optional[Callable[[float], float]] = None
        self._on_light_callbacks: list[Callable] = []

    def override_wall_color(self, wall_type: int,
                            color: Tuple[int, int, int]) -> None:
        """!@brief 覆盖指定墙类型的颜色

        @param wall_type 墙类型（1=普通，2=出口，或自定义类型）
        @param color     RGB颜色元组
        """
        self._wall_color_overrides[wall_type] = color

    def remove_wall_color_override(self, wall_type: int) -> None:
        """!@brief 移除墙颜色覆盖"""
        self._wall_color_overrides.pop(wall_type, None)

    def set_fog_factor_fn(self, fn: Callable[[float], float]) -> None:
        """!@brief 设置自定义雾化因子函数

        @param fn 函数签名 fn(distance: float) -> float，返回[0,1]亮度因子
        """
        self._fog_factor_fn = fn

    def on_light_calc(self, callback: Callable) -> None:
        """!@brief 注册光照计算回调"""
        self._on_light_callbacks.append(callback)

    def get_wall_base_color(self, hit) -> Tuple[int, int, int]:
        """!@brief 获取墙面基础颜色（支持覆盖）"""
        if hit.wall_type in self._wall_color_overrides:
            return self._wall_color_overrides[hit.wall_type]
        if hit.wall_type == 2:
            return EXIT_COLOR
        elif hit.side == 0:
            return WALL_NS_COLOR
        else:
            return WALL_EW_COLOR

    @staticmethod
    def _lerp(c1, c2, t):
        """!@brief 线性插值两个颜色"""
        t = max(0.0, min(1.0, t))
        return (int(c1[0] + (c2[0] - c1[0]) * t),
                int(c1[1] + (c2[1] - c1[1]) * t),
                int(c1[2] + (c2[2] - c1[2]) * t))

    @staticmethod
    def _apply_brightness(color, brightness):
        """!@brief 按亮度系数缩放颜色"""
        b = max(0.0, brightness)
        return (min(255, int(color[0] * b)),
                min(255, int(color[1] * b)),
                min(255, int(color[2] * b)))

    @staticmethod
    def fog_factor(distance):
        """!@brief 计算距离雾化亮度因子"""
        if distance <= FOG_NEAR:
            return 1.0
        if distance >= FOG_FAR:
            return MIN_BRIGHTNESS
        t = (distance - FOG_NEAR) / (FOG_FAR - FOG_NEAR)
        t = t ** FOG_GAMMA
        return 1.0 - t * (1.0 - MIN_BRIGHTNESS)

    def compute_fog(self, distance: float) -> float:
        """!@brief 计算雾化因子（支持自定义覆盖）"""
        if self._fog_factor_fn is not None:
            return self._fog_factor_fn(distance)
        return self.fog_factor(distance)

    def ceiling_color(self, y, horizon, pixel_height):
        """!@brief 计算天花板行颜色（含雾化与量化）"""
        t = y / horizon if horizon > 0 else 0
        base = self._lerp(CEILING_TOP, CEILING_BOTTOM, t)
        dy = horizon - y
        fog = self.compute_fog(PLAYER_EYE_HEIGHT * pixel_height / dy) if dy > 0.5 else 1.0
        c = self._apply_brightness(base, fog)
        qtab = self._qtab
        return (qtab[c[0]], qtab[c[1]], qtab[c[2]])

    def floor_color(self, y, horizon, pixel_height):
        """!@brief 计算地板行颜色（含雾化与量化）"""
        floor_denom = pixel_height - horizon
        t = (y - horizon) / floor_denom if floor_denom > 0 else 0
        base = self._lerp(FLOOR_TOP, FLOOR_BOTTOM, t)
        dy = y - horizon
        fog = self.compute_fog(PLAYER_EYE_HEIGHT * pixel_height / dy) if dy > 0.5 else 1.0
        c = self._apply_brightness(base, fog)
        qtab = self._qtab
        return (qtab[c[0]], qtab[c[1]], qtab[c[2]])

    def wall_color(self, hit, vertical_t):
        """!@brief 计算墙面像素颜色"""
        base = self.get_wall_base_color(hit)

        fog = self.compute_fog(hit.distance)
        side_shade = 1.0 if hit.side == 0 else WALL_SIDE_SHADE

        stripe = 1.0
        if WALL_STRIPE_PERIOD > 0:
            phase = hit.wall_x / WALL_STRIPE_PERIOD
            stripe = 1.0 - WALL_STRIPE_CONTRAST * (0.5 - 0.5 * math.cos(phase * 2.0 * math.pi))

        vert_curve = 4.0 * vertical_t * (1.0 - vertical_t)
        vert_shade = 1.0 - WALL_VERTICAL_SHADE * (1.0 - vert_curve)

        brightness = fog * side_shade * stripe * vert_shade
        return self._apply_brightness(base, brightness)

    def quantize(self, r, g, b):
        """!@brief 量化颜色值"""
        qtab = self._qtab
        return (qtab[r], qtab[g], qtab[b])
