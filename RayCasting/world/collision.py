"""!
@file world/collision.py
@brief 碰撞检测系统

提供可扩展的碰撞检测接口与默认实现。
支持注册自定义碰撞层和碰撞响应。
"""

from abc import ABC, abstractmethod
from typing import Callable, Optional
from core import log_manager

_logger = log_manager.get_logger('world.collision')


class CollisionLayer:
    """!@brief 碰撞层常量"""
    WALL = 'wall'
    ENTITY = 'entity'
    TRIGGER = 'trigger'
    PROJECTILE = 'projectile'


class CollisionResult:
    """!@brief 碰撞检测结果"""

    __slots__ = ('hit', 'point_x', 'point_y', 'normal_x', 'normal_y',
                 'layer', 'entity_id', 'distance')

    def __init__(self, hit: bool = False, point_x: float = 0.0,
                 point_y: float = 0.0, normal_x: float = 0.0,
                 normal_y: float = 0.0, layer: str = '',
                 entity_id: str = '', distance: float = 0.0):
        self.hit = hit
        self.point_x = point_x
        self.point_y = point_y
        self.normal_x = normal_x
        self.normal_y = normal_y
        self.layer = layer
        self.entity_id = entity_id
        self.distance = distance


class CollisionChecker(ABC):
    """!@brief 碰撞检测器协议"""

    @abstractmethod
    def check_point(self, x: float, y: float) -> CollisionResult:
        """!@brief 检测点是否碰撞"""
        ...

    @abstractmethod
    def check_circle(self, x: float, y: float, radius: float) -> CollisionResult:
        """!@brief 检测圆是否碰撞"""
        ...

    @abstractmethod
    def check_line(self, x1: float, y1: float,
                   x2: float, y2: float) -> CollisionResult:
        """!@brief 检测线段是否碰撞"""
        ...


class WallCollisionChecker(CollisionChecker):
    """!@brief 墙壁碰撞检测器

    基于迷宫网格的碰撞检测。
    """

    def __init__(self, maze):
        self._maze = maze

    def check_point(self, x: float, y: float) -> CollisionResult:
        if self._maze.is_wall(x, y):
            return CollisionResult(hit=True, point_x=x, point_y=y,
                                   layer=CollisionLayer.WALL)
        return CollisionResult(hit=False)

    def check_circle(self, x: float, y: float, radius: float) -> CollisionResult:
        import math
        for angle in range(0, 360, 45):
            rad = math.radians(angle)
            cx = x + math.cos(rad) * radius
            cy = y + math.sin(rad) * radius
            if self._maze.is_wall(cx, cy):
                return CollisionResult(hit=True, point_x=cx, point_y=cy,
                                       layer=CollisionLayer.WALL)
        return CollisionResult(hit=False)

    def check_line(self, x1: float, y1: float,
                   x2: float, y2: float) -> CollisionResult:
        import math
        dist = math.hypot(x2 - x1, y2 - y1)
        steps = max(1, int(dist * 4))
        for i in range(steps + 1):
            t = i / steps
            px = x1 + (x2 - x1) * t
            py = y1 + (y2 - y1) * t
            if self._maze.is_wall(px, py):
                return CollisionResult(hit=True, point_x=px, point_y=py,
                                       distance=t * dist,
                                       layer=CollisionLayer.WALL)
        return CollisionResult(hit=False)


class CollisionSystem:
    """!@brief 碰撞系统

    管理多个碰撞检测器，支持分层检测与碰撞响应回调。
    """

    def __init__(self):
        self._checkers: dict[str, CollisionChecker] = {}
        self._response_handlers: dict[str, list[Callable]] = {}

    def register_checker(self, layer: str, checker: CollisionChecker) -> None:
        """!@brief 注册碰撞检测器"""
        self._checkers[layer] = checker

    def unregister_checker(self, layer: str) -> None:
        """!@brief 注销碰撞检测器"""
        self._checkers.pop(layer, None)

    def check_point(self, x: float, y: float,
                    layers: Optional[list[str]] = None) -> CollisionResult:
        """!@brief 检测点碰撞"""
        for layer, checker in self._checkers.items():
            if layers is not None and layer not in layers:
                continue
            result = checker.check_point(x, y)
            if result.hit:
                result.layer = layer
                self._fire_response(layer, result)
                return result
        return CollisionResult(hit=False)

    def check_circle(self, x: float, y: float, radius: float,
                     layers: Optional[list[str]] = None) -> CollisionResult:
        """!@brief 检测圆碰撞"""
        for layer, checker in self._checkers.items():
            if layers is not None and layer not in layers:
                continue
            result = checker.check_circle(x, y, radius)
            if result.hit:
                result.layer = layer
                self._fire_response(layer, result)
                return result
        return CollisionResult(hit=False)

    def on_collision(self, layer: str, handler: Callable[[CollisionResult], None]) -> None:
        """!@brief 注册碰撞响应"""
        if layer not in self._response_handlers:
            self._response_handlers[layer] = []
        self._response_handlers[layer].append(handler)

    def _fire_response(self, layer: str, result: CollisionResult) -> None:
        for handler in self._response_handlers.get(layer, []):
            try:
                handler(result)
            except Exception as e:
                _logger.error('碰撞响应异常: %s: %s', layer, e)
