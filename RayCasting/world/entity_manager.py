"""!
@file world/entity_manager.py
@brief 实体管理器

统一管理实体生命周期、空间索引、对象池。
提供链式查询、空间查询、实体分组等功能。
"""

import random
from typing import Any, Callable, Optional

from core import log_manager

_logger = log_manager.get_logger('world.entity_manager')


class EntityQuery:
    """!@brief 实体查询构建器 - 链式调用"""

    def __init__(self, entities: dict):
        self._entities = entities
        self._tag_filter = None
        self._component_filter = None
        self._radius_filter = None
        self._center = None
        self._active_only = True

    def with_tag(self, tag: str) -> 'EntityQuery':
        self._tag_filter = tag
        return self

    def with_component(self, type_name: str) -> 'EntityQuery':
        self._component_filter = type_name
        return self

    def in_radius(self, x: float, y: float, radius: float) -> 'EntityQuery':
        self._radius_filter = radius
        self._center = (x, y)
        return self

    def include_inactive(self) -> 'EntityQuery':
        self._active_only = False
        return self

    def execute(self) -> list:
        results = list(self._entities.values())
        if self._active_only:
            results = [e for e in results if e.active]
        if self._tag_filter:
            results = [e for e in results if e.has_tag(self._tag_filter)]
        if self._component_filter:
            results = [e for e in results if e.has_component(self._component_filter)]
        if self._radius_filter and self._center:
            cx, cy = self._center
            r2 = self._radius_filter * self._radius_filter
            results = [e for e in results
                       if (e.x - cx) ** 2 + (e.y - cy) ** 2 <= r2]
        return results

    def first(self) -> Optional[Any]:
        results = self.execute()
        return results[0] if results else None

    def count(self) -> int:
        return len(self.execute())


class EntityPool:
    """!@brief 实体对象池 - 减少频繁创建/销毁的GC压力"""

    def __init__(self, factory: Callable[[], Any], initial_size: int = 10):
        self._factory = factory
        self._pool: list = []
        self._active: dict[str, Any] = {}
        for _ in range(initial_size):
            self._pool.append(self._factory())

    def acquire(self, entity_id: str, x: float = 0.0, y: float = 0.0,
                angle: float = 0.0) -> Any:
        if self._pool:
            entity = self._pool.pop()
        else:
            entity = self._factory()
        entity.id = entity_id
        entity.x = x
        entity.y = y
        entity.angle = angle
        entity.active = True
        entity.visible = True
        self._active[entity_id] = entity
        return entity

    def release(self, entity_id: str) -> Optional[Any]:
        entity = self._active.pop(entity_id, None)
        if entity is not None:
            entity.active = False
            entity.visible = False
            for comp in entity.components:
                comp.on_detach(entity)
            entity._components.clear()
            entity._tags.clear()
            entity._properties.clear()
            self._pool.append(entity)
        return entity

    @property
    def active_count(self) -> int:
        return len(self._active)

    @property
    def pooled_count(self) -> int:
        return len(self._pool)


class SpatialGrid:
    """!@brief 空间哈希网格 - 加速空间查询"""

    def __init__(self, cell_size: float = 5.0):
        self._cell_size = cell_size
        self._grid: dict[tuple[int, int], list] = {}

    def _cell_key(self, x: float, y: float) -> tuple[int, int]:
        return (int(x // self._cell_size), int(y // self._cell_size))

    def insert(self, entity) -> None:
        key = self._cell_key(entity.x, entity.y)
        if key not in self._grid:
            self._grid[key] = []
        self._grid[key].append(entity)

    def remove(self, entity) -> None:
        key = self._cell_key(entity.x, entity.y)
        if key in self._grid:
            try:
                self._grid[key].remove(entity)
            except ValueError:
                pass

    def update(self, entity, old_x: float, old_y: float) -> None:
        old_key = self._cell_key(old_x, old_y)
        new_key = self._cell_key(entity.x, entity.y)
        if old_key != new_key:
            self._remove_from_cell(entity, old_key)
            self.insert(entity)

    def _remove_from_cell(self, entity, key: tuple) -> None:
        if key in self._grid:
            try:
                self._grid[key].remove(entity)
            except ValueError:
                pass

    def query_radius(self, x: float, y: float, radius: float) -> list:
        results = []
        min_cx = int((x - radius) // self._cell_size)
        max_cx = int((x + radius) // self._cell_size)
        min_cy = int((y - radius) // self._cell_size)
        max_cy = int((y + radius) // self._cell_size)
        r2 = radius * radius
        for cx in range(min_cx, max_cx + 1):
            for cy in range(min_cy, max_cy + 1):
                for entity in self._grid.get((cx, cy), []):
                    if (entity.x - x) ** 2 + (entity.y - y) ** 2 <= r2:
                        results.append(entity)
        return results

    def query_cell(self, x: float, y: float) -> list:
        return self._grid.get(self._cell_key(x, y), [])

    def clear(self) -> None:
        self._grid.clear()


class EntityManager:
    """!@brief 实体管理器

    统一管理实体生命周期、空间索引、对象池。
    提供链式查询、空间查询、实体分组等功能。
    """

    def __init__(self, event_bus=None):
        self._events = event_bus
        self._entities: dict[str, Any] = {}
        self._spatial = SpatialGrid()
        self._pools: dict[str, EntityPool] = {}
        self._groups: dict[str, set[str]] = {}

    def add(self, entity, group: str = None) -> None:
        self._entities[entity.id] = entity
        self._spatial.insert(entity)
        if group:
            if group not in self._groups:
                self._groups[group] = set()
            self._groups[group].add(entity.id)
        if self._events:
            self._events.publish('entity.spawned', {
                'entity_id': entity.id, 'x': entity.x, 'y': entity.y
            })

    def remove(self, entity_id: str) -> Optional[Any]:
        entity = self._entities.pop(entity_id, None)
        if entity is not None:
            self._spatial.remove(entity)
            for group in self._groups.values():
                group.discard(entity_id)
            if self._events:
                self._events.publish('entity.destroyed', {
                    'entity_id': entity_id
                })
        return entity

    def get(self, entity_id: str) -> Optional[Any]:
        return self._entities.get(entity_id)

    def query(self) -> EntityQuery:
        return EntityQuery(self._entities)

    def query_radius(self, x: float, y: float, radius: float) -> list:
        return self._spatial.query_radius(x, y, radius)

    def get_group(self, group: str) -> list:
        ids = self._groups.get(group, set())
        return [self._entities[eid] for eid in ids if eid in self._entities]

    def register_pool(self, name: str, factory: Callable[[], Any],
                      initial_size: int = 10) -> None:
        self._pools[name] = EntityPool(factory, initial_size)

    def spawn_from_pool(self, pool_name: str, entity_id: str,
                        x: float = 0.0, y: float = 0.0,
                        angle: float = 0.0, group: str = None) -> Optional[Any]:
        pool = self._pools.get(pool_name)
        if pool is None:
            return None
        entity = pool.acquire(entity_id, x, y, angle)
        self.add(entity, group)
        return entity

    def return_to_pool(self, pool_name: str, entity_id: str) -> None:
        pool = self._pools.get(pool_name)
        if pool is None:
            return
        entity = self._entities.get(entity_id)
        if entity:
            self._spatial.remove(entity)
        pool.release(entity_id)
        self._entities.pop(entity_id, None)
        for g in self._groups.values():
            g.discard(entity_id)

    def update_all(self, delta_time: float) -> None:
        for entity in list(self._entities.values()):
            if entity.active:
                old_x, old_y = entity.x, entity.y
                entity.update(delta_time)
                if entity.x != old_x or entity.y != old_y:
                    self._spatial.update(entity, old_x, old_y)

    @property
    def count(self) -> int:
        return len(self._entities)

    @property
    def entities(self) -> list:
        return list(self._entities.values())

    def clear(self) -> None:
        self._entities.clear()
        self._spatial.clear()
        self._groups.clear()
