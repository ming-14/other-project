"""!
@file world/__init__.py
@brief 世界模块包

导出世界层核心类。
"""

from world.entity import Entity, Component, MovementComponent, HealthComponent, InventoryComponent
from world.collision import (CollisionSystem, CollisionChecker, CollisionResult,
                             WallCollisionChecker, CollisionLayer)
from world.maze import Maze
from world.player import Player
from world.raycaster import Raycaster, RayHit
from world.world_manager import WorldManager

__all__ = [
    'Entity', 'Component', 'MovementComponent', 'HealthComponent', 'InventoryComponent',
    'CollisionSystem', 'CollisionChecker', 'CollisionResult',
    'WallCollisionChecker', 'CollisionLayer',
    'Maze', 'Player', 'Raycaster', 'RayHit', 'WorldManager',
]
