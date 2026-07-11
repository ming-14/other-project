"""!
@file world/raycaster.py
@brief 光线投射引擎模块

使用DDA(Digital Differential Analysis)算法对屏幕每一列投射光线，
计算与墙壁的垂直距离，用于后续渲染墙面高度。
支持自定义光线过滤器与命中回调。
"""

import math
from typing import Callable, Optional

from core import log_manager

_logger = log_manager.get_logger('world.raycaster')


class RayHit:
    """!@brief 单条光线命中结果"""

    __slots__ = ('distance', 'side', 'wall_type', 'wall_x')

    def __init__(self, distance, side, wall_type, wall_x):
        """!@brief 构造命中结果

        @param distance  垂直距离（已消除鱼眼畸变）
        @param side      命中墙面朝向：0=南北墙(X面)，1=东西墙(Y面)
        @param wall_type 命中单元格类型（1=普通墙，2=出口）
        @param wall_x    命中点在墙面上的横向坐标(0~1)，用于纹理映射
        """
        self.distance = distance
        self.side = side
        self.wall_type = wall_type
        self.wall_x = wall_x


class Raycaster:
    """!@brief 光线投射器

    支持自定义命中过滤器和命中后回调。
    """

    def __init__(self, maze):
        self.maze = maze
        self._hit_filters: list[Callable[[RayHit], bool]] = []
        self._on_hit_callbacks: list[Callable[[int, RayHit], None]] = []
        self._max_steps_override: Optional[int] = None

    def add_hit_filter(self, filter_fn: Callable[[RayHit], bool]) -> None:
        """!@brief 添加命中过滤器

        @param filter_fn 过滤函数，返回True表示接受此命中
        """
        self._hit_filters.append(filter_fn)

    def add_on_hit(self, callback: Callable[[int, RayHit], None]) -> None:
        """!@brief 添加命中回调

        @param callback 回调函数 callback(col: int, hit: RayHit)
        """
        self._on_hit_callbacks.append(callback)

    def set_max_steps(self, max_steps: Optional[int]) -> None:
        """!@brief 设置DDA最大步数"""
        self._max_steps_override = max_steps

    def cast(self, px, py, dir_x, dir_y, plane_x, plane_y, screen_width):
        """!@brief 对整屏投射光线，返回每列命中结果列表"""
        hits = []
        for col in range(screen_width):
            camera_x = 2.0 * col / screen_width - 1.0
            ray_dir_x = dir_x + plane_x * camera_x
            ray_dir_y = dir_y + plane_y * camera_x
            hit = self._cast_single(px, py, ray_dir_x, ray_dir_y)
            hits.append(hit)
            for cb in self._on_hit_callbacks:
                cb(col, hit)
        return hits

    def _cast_single(self, px, py, ray_dir_x, ray_dir_y):
        """!@brief 投射单条光线并执行DDA"""
        map_x = int(px)
        map_y = int(py)

        delta_dist_x = self._safe_inverse(ray_dir_x)
        delta_dist_y = self._safe_inverse(ray_dir_y)

        if ray_dir_x < 0:
            step_x = -1
            side_dist_x = (px - map_x) * delta_dist_x
        else:
            step_x = 1
            side_dist_x = (map_x + 1.0 - px) * delta_dist_x

        if ray_dir_y < 0:
            step_y = -1
            side_dist_y = (py - map_y) * delta_dist_y
        else:
            step_y = 1
            side_dist_y = (map_y + 1.0 - py) * delta_dist_y

        hit = False
        side = 0
        wall_type = 1
        max_steps = (self._max_steps_override or
                     (self.maze.width + self.maze.height + 4))
        steps = 0
        while not hit and steps < max_steps:
            steps += 1
            if side_dist_x < side_dist_y:
                side_dist_x += delta_dist_x
                map_x += step_x
                side = 0
            else:
                side_dist_y += delta_dist_y
                map_y += step_y
                side = 1
            cell = self.maze.cell_type(map_x, map_y)
            if cell >= 1:
                hit = True
                wall_type = cell

        if side == 0:
            perp_dist = side_dist_x - delta_dist_x
        else:
            perp_dist = side_dist_y - delta_dist_y

        if perp_dist < 1e-6:
            perp_dist = 1e-6

        if side == 0:
            wall_x = py + perp_dist * ray_dir_y
        else:
            wall_x = px + perp_dist * ray_dir_x
        wall_x -= math.floor(wall_x)

        result = RayHit(perp_dist, side, wall_type, wall_x)

        for filter_fn in self._hit_filters:
            if not filter_fn(result):
                return RayHit(perp_dist, side, 0, wall_x)

        return result

    @staticmethod
    def _safe_inverse(value):
        """!@brief 安全计算1/|value|，value为0时返回大数"""
        if abs(value) < 1e-6:
            return 1e30
        return abs(1.0 / value)
