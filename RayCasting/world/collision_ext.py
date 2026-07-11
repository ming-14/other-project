"""!
@file world/collision_ext.py
@brief 碰撞系统扩展

提供实体碰撞检测器、触发区域系统等扩展功能。
依赖EntityManager的空间查询能力。
"""

from typing import Callable, Optional

from world.collision import CollisionChecker, CollisionResult, CollisionLayer
from world.entity_manager import EntityManager
from core import log_manager

_logger = log_manager.get_logger('world.collision_ext')


class SimpleCollisionChecker(CollisionChecker):
    """!@brief 简化碰撞检测器 - 只需传入check_point函数"""

    def __init__(self, check_fn: Callable[[float, float], CollisionResult]):
        self._check_fn = check_fn

    def check_point(self, x, y) -> CollisionResult:
        return self._check_fn(x, y)

    def check_circle(self, x, y, radius) -> CollisionResult:
        return self.check_point(x, y)

    def check_line(self, x1, y1, x2, y2) -> CollisionResult:
        return self.check_point(x1, y1)


class EntityCollisionChecker(CollisionChecker):
    """!@brief 实体碰撞检测器 - 基于EntityManager空间查询"""

    def __init__(self, entity_manager: EntityManager,
                 target_tag: str = None,
                 target_component: str = None,
                 collision_radius: float = 0.5):
        self._manager = entity_manager
        self._target_tag = target_tag
        self._target_component = target_component
        self._radius = collision_radius

    def check_point(self, x, y) -> CollisionResult:
        nearby = self._manager.query_radius(x, y, self._radius)
        for entity in nearby:
            if self._target_tag and not entity.has_tag(self._target_tag):
                continue
            if self._target_component and not entity.has_component(self._target_component):
                continue
            dist_sq = (entity.x - x) ** 2 + (entity.y - y) ** 2
            if dist_sq < self._radius * self._radius:
                import math
                dist = math.sqrt(dist_sq)
                return CollisionResult(
                    hit=True, point_x=entity.x, point_y=entity.y,
                    layer='entity', entity_id=entity.id, distance=dist)
        return CollisionResult(hit=False)

    def check_circle(self, x, y, radius) -> CollisionResult:
        search_r = radius + self._radius
        nearby = self._manager.query_radius(x, y, search_r)
        for entity in nearby:
            if self._target_tag and not entity.has_tag(self._target_tag):
                continue
            if self._target_component and not entity.has_component(self._target_component):
                continue
            import math
            dist = math.sqrt((entity.x - x) ** 2 + (entity.y - y) ** 2)
            if dist < radius + self._radius:
                return CollisionResult(
                    hit=True, point_x=entity.x, point_y=entity.y,
                    layer='entity', entity_id=entity.id, distance=dist)
        return CollisionResult(hit=False)

    def check_line(self, x1, y1, x2, y2) -> CollisionResult:
        return self.check_point(x1, y1)


class TriggerZone:
    """!@brief 触发区域 - 玩家进入时触发事件"""

    def __init__(self, zone_id: str, x: float, y: float,
                 radius: float, event_type: str, data: dict = None):
        self.zone_id = zone_id
        self.x = x
        self.y = y
        self.radius = radius
        self.event_type = event_type
        self.data = data or {}
        self.one_shot = True
        self.triggered = False
        self.cooldown = 0.0
        self._cooldown_timer = 0.0

    def check(self, px: float, py: float, delta_time: float = 0) -> bool:
        if self.triggered and self.one_shot:
            return False
        if self._cooldown_timer > 0:
            self._cooldown_timer -= delta_time
            return False
        dist_sq = (px - self.x) ** 2 + (py - self.y) ** 2
        if dist_sq <= self.radius * self.radius:
            if self.one_shot:
                self.triggered = True
            self._cooldown_timer = self.cooldown
            return True
        return False


class TriggerSystem:
    """!@brief 触发区域系统"""

    def __init__(self, event_bus):
        self._events = event_bus
        self._zones: list[TriggerZone] = []

    def add_zone(self, zone: TriggerZone) -> None:
        self._zones.append(zone)

    def remove_zone(self, zone_id: str) -> None:
        self._zones = [z for z in self._zones if z.zone_id != zone_id]

    def update(self, player_x: float, player_y: float,
               delta_time: float) -> None:
        for zone in self._zones:
            if zone.check(player_x, player_y, delta_time):
                self._events.publish(zone.event_type, {
                    'zone_id': zone.zone_id,
                    'x': zone.x, 'y': zone.y,
                    **zone.data
                })

    def clear(self) -> None:
        self._zones.clear()
