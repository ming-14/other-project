"""!
@file world/world_manager.py
@brief 世界管理器

统一管理迷宫、实体、碰撞等世界状态，
提供世界级的查询与操作接口。
"""

from typing import Callable, Optional
from core import log_manager
from core.event_bus import EventBus, EventType
from world.entity import Entity
from world.collision import CollisionSystem, WallCollisionChecker
from world.generators.base import MazeGenerator
from world.generators.recursive_backtrack import RecursiveBacktrackGenerator

_logger = log_manager.get_logger('world.world_manager')


class WorldManager:
    """!@brief 世界管理器

    管理迷宫生成、实体生命周期、碰撞系统。
    提供世界级的查询与操作API。
    """

    def __init__(self, events: EventBus):
        self._events = events
        self._maze = None
        self._entities: dict[str, Entity] = {}
        self._collision = CollisionSystem()
        self._generators: dict[str, MazeGenerator] = {}
        self._active_generator: Optional[str] = None
        self._on_maze_generated_callbacks: list[Callable] = []
        self._on_entity_added_callbacks: list[Callable] = []
        self._on_entity_removed_callbacks: list[Callable] = []
        self._register_default_generators()

    def _register_default_generators(self) -> None:
        gen = RecursiveBacktrackGenerator()
        self._generators[gen.name] = gen
        self._active_generator = gen.name

    def register_generator(self, generator: MazeGenerator) -> None:
        """!@brief 注册自定义迷宫生成器"""
        self._generators[generator.name] = generator

    def set_generator(self, name: str) -> bool:
        """!@brief 设置当前使用的生成器"""
        if name in self._generators:
            self._active_generator = name
            return True
        return False

    def generate_maze(self, width: int, height: int,
                      seed: Optional[int] = None) -> None:
        """!@brief 生成迷宫"""
        gen = self._generators.get(self._active_generator)
        if gen is None:
            _logger.error('无可用生成器: %s', self._active_generator)
            return
        from world.maze import Maze
        self._maze = Maze(width=width, height=height, seed=seed,
                          generator=gen)
        self._collision.register_checker(
            'wall', WallCollisionChecker(self._maze))
        self._events.publish(EventType.WORLD_MAZE_GENERATED, {
            'width': width, 'height': height, 'seed': seed,
        })
        for cb in self._on_maze_generated_callbacks:
            cb(self._maze)

    def regenerate(self, seed: Optional[int] = None) -> None:
        """!@brief 用相同尺寸重新生成迷宫"""
        if self._maze is None:
            return
        self.generate_maze(self._maze.width, self._maze.height, seed)

    @property
    def maze(self):
        """!@brief 获取当前迷宫"""
        return self._maze

    @property
    def collision(self) -> CollisionSystem:
        """!@brief 获取碰撞系统"""
        return self._collision

    # ========================================================================
    # 实体管理
    # ========================================================================

    def add_entity(self, entity: Entity) -> None:
        """!@brief 添加实体到世界"""
        self._entities[entity.id] = entity
        for cb in self._on_entity_added_callbacks:
            cb(entity)

    def remove_entity(self, entity_id: str) -> Optional[Entity]:
        """!@brief 从世界移除实体"""
        entity = self._entities.pop(entity_id, None)
        if entity is not None:
            for cb in self._on_entity_removed_callbacks:
                cb(entity)
        return entity

    def get_entity(self, entity_id: str) -> Optional[Entity]:
        """!@brief 获取实体"""
        return self._entities.get(entity_id)

    def find_entities_by_tag(self, tag: str) -> list[Entity]:
        """!@brief 按标签查找实体"""
        return [e for e in self._entities.values() if e.has_tag(tag)]

    def find_entities_by_component(self, component_type: str) -> list[Entity]:
        """!@brief 按组件类型查找实体"""
        return [e for e in self._entities.values()
                if e.has_component(component_type)]

    @property
    def entities(self) -> list[Entity]:
        """!@brief 所有实体列表"""
        return list(self._entities.values())

    def update_entities(self, delta_time: float) -> None:
        """!@brief 更新所有活跃实体"""
        for entity in self._entities.values():
            if entity.active:
                entity.update(delta_time)

    # ========================================================================
    # 回调注册
    # ========================================================================

    def on_maze_generated(self, callback: Callable) -> None:
        """!@brief 注册迷宫生成回调"""
        self._on_maze_generated_callbacks.append(callback)

    def on_entity_added(self, callback: Callable) -> None:
        """!@brief 注册实体添加回调"""
        self._on_entity_added_callbacks.append(callback)

    def on_entity_removed(self, callback: Callable) -> None:
        """!@brief 注册实体移除回调"""
        self._on_entity_removed_callbacks.append(callback)
