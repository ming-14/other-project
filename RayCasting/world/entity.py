"""!
@file world/entity.py
@brief 实体系统

定义游戏世界中的实体基类与组件系统，
支持自定义实体类型（玩家、NPC、道具等）。
"""

import math
from abc import ABC, abstractmethod
from typing import Any, Callable, Optional
from core import log_manager

_logger = log_manager.get_logger('world.entity')


class Component(ABC):
    """!@brief 实体组件协议

    可附加到实体的功能模块，如移动、碰撞、血量等。
    """

    @property
    def type_name(self) -> str:
        """!@brief 组件类型名"""
        return self.__class__.__name__

    @abstractmethod
    def on_attach(self, entity: 'Entity') -> None:
        """!@brief 附加到实体时调用"""
        ...

    @abstractmethod
    def on_detach(self, entity: 'Entity') -> None:
        """!@brief 从实体分离时调用"""
        ...

    def on_update(self, entity: 'Entity', delta_time: float) -> None:
        """!@brief 每帧更新（可选覆盖）"""
        pass


class Entity:
    """!@brief 游戏实体

    组合式实体，通过附加Component实现不同行为。
    """

    def __init__(self, entity_id: str, x: float = 0.0, y: float = 0.0,
                 angle: float = 0.0):
        self.id = entity_id
        self.x = float(x)
        self.y = float(y)
        self.angle = float(angle)
        self.pitch = 0.0
        self.active = True
        self.visible = True
        self._components: dict[str, Component] = {}
        self._tags: set[str] = set()
        self._properties: dict[str, Any] = {}

    def attach(self, component: Component) -> None:
        """!@brief 附加组件"""
        type_name = component.type_name
        if type_name in self._components:
            self.detach(type_name)
        self._components[type_name] = component
        component.on_attach(self)

    def detach(self, type_name: str) -> Optional[Component]:
        """!@brief 分离组件"""
        comp = self._components.pop(type_name, None)
        if comp is not None:
            comp.on_detach(self)
        return comp

    def get_component(self, type_name: str) -> Optional[Component]:
        """!@brief 获取组件"""
        return self._components.get(type_name)

    def has_component(self, type_name: str) -> bool:
        """!@brief 是否拥有指定组件"""
        return type_name in self._components

    def add_tag(self, tag: str) -> None:
        """!@brief 添加标签"""
        self._tags.add(tag)

    def has_tag(self, tag: str) -> bool:
        """!@brief 是否拥有标签"""
        return tag in self._tags

    def set_property(self, key: str, value: Any) -> None:
        """!@brief 设置自定义属性"""
        self._properties[key] = value

    def get_property(self, key: str, default: Any = None) -> Any:
        """!@brief 获取自定义属性"""
        return self._properties.get(key, default)

    def update(self, delta_time: float) -> None:
        """!@brief 更新所有组件"""
        for comp in self._components.values():
            comp.on_update(self, delta_time)

    @property
    def dir_vector(self) -> tuple:
        """!@brief 朝向单位向量"""
        return (math.cos(self.angle), math.sin(self.angle))

    @property
    def plane_vector(self) -> tuple:
        """!@brief 相机平面向量"""
        import config
        half_tan = math.tan(config.FOV / 2.0)
        return (-math.sin(self.angle) * half_tan,
                math.cos(self.angle) * half_tan)

    @property
    def components(self) -> list[Component]:
        """!@brief 所有组件列表"""
        return list(self._components.values())


class MovementComponent(Component):
    """!@brief 移动组件

    处理实体的前进/后退/平移/旋转，带碰撞检测。
    """

    def __init__(self, move_speed: float = 0.06, rotate_speed: float = 0.045,
                 wall_padding: float = 0.2, sprint_multiplier: float = 1.8):
        self.move_speed = move_speed
        self.rotate_speed = rotate_speed
        self.wall_padding = wall_padding
        self.sprint_multiplier = sprint_multiplier
        self.is_sprinting = False
        self._collision_fn: Optional[Callable] = None

    def on_attach(self, entity: Entity) -> None:
        pass

    def on_detach(self, entity: Entity) -> None:
        pass

    def set_collision_fn(self, fn: Callable[[float, float], bool]) -> None:
        """!@brief 设置碰撞检测函数"""
        self._collision_fn = fn

    def _can_move_to(self, nx: float, ny: float) -> bool:
        if self._collision_fn is None:
            return True
        pad = self.wall_padding
        for cx, cy in ((nx - pad, ny - pad), (nx + pad, ny - pad),
                       (nx - pad, ny + pad), (nx + pad, ny + pad)):
            if self._collision_fn(cx, cy):
                return False
        return True

    def move_forward(self, entity: Entity, distance: float = 0.0) -> None:
        """!@brief 沿朝向前进"""
        if distance == 0.0:
            speed = self.move_speed
            if self.is_sprinting:
                speed *= self.sprint_multiplier
            distance = speed
        nx = entity.x + math.cos(entity.angle) * distance
        ny = entity.y + math.sin(entity.angle) * distance
        if self._can_move_to(nx, entity.y):
            entity.x = nx
        if self._can_move_to(entity.x, ny):
            entity.y = ny

    def strafe(self, entity: Entity, distance: float = 0.0) -> None:
        """!@brief 左右平移"""
        if distance == 0.0:
            distance = self.move_speed
        nx = entity.x - math.sin(entity.angle) * distance
        ny = entity.y + math.cos(entity.angle) * distance
        if self._can_move_to(nx, entity.y):
            entity.x = nx
        if self._can_move_to(entity.x, ny):
            entity.y = ny

    def rotate(self, entity: Entity, angle_delta: float = 0.0) -> None:
        """!@brief 旋转"""
        if angle_delta == 0.0:
            angle_delta = self.rotate_speed
        entity.angle += angle_delta

    def adjust_pitch(self, entity: Entity, delta: float) -> None:
        """!@brief 调整俯仰角"""
        import config
        entity.pitch += delta
        if entity.pitch > config.PITCH_MAX:
            entity.pitch = config.PITCH_MAX
        elif entity.pitch < -config.PITCH_MAX:
            entity.pitch = -config.PITCH_MAX


class HealthComponent(Component):
    """!@brief 血量组件"""

    def __init__(self, max_health: float = 100.0):
        self.max_health = max_health
        self.health = max_health
        self.alive = True
        self._on_death_callbacks: list[Callable] = []

    def on_attach(self, entity: Entity) -> None:
        pass

    def on_detach(self, entity: Entity) -> None:
        pass

    def take_damage(self, amount: float) -> None:
        """!@brief 受到伤害"""
        if not self.alive:
            return
        self.health = max(0.0, self.health - amount)
        if self.health <= 0:
            self.alive = False
            for cb in self._on_death_callbacks:
                cb()

    def heal(self, amount: float) -> None:
        """!@brief 治疗"""
        if not self.alive:
            return
        self.health = min(self.max_health, self.health + amount)

    def on_death(self, callback: Callable) -> None:
        """!@brief 注册死亡回调"""
        self._on_death_callbacks.append(callback)


class InventoryComponent(Component):
    """!@brief 背包组件"""

    def __init__(self, capacity: int = 20):
        self.capacity = capacity
        self._items: dict[str, int] = {}

    def on_attach(self, entity: Entity) -> None:
        pass

    def on_detach(self, entity: Entity) -> None:
        pass

    def add_item(self, item_id: str, count: int = 1) -> bool:
        """!@brief 添加物品"""
        if len(self._items) >= self.capacity and item_id not in self._items:
            return False
        self._items[item_id] = self._items.get(item_id, 0) + count
        return True

    def remove_item(self, item_id: str, count: int = 1) -> bool:
        """!@brief 移除物品"""
        current = self._items.get(item_id, 0)
        if current < count:
            return False
        self._items[item_id] = current - count
        if self._items[item_id] <= 0:
            del self._items[item_id]
        return True

    def has_item(self, item_id: str, count: int = 1) -> bool:
        """!@brief 是否拥有物品"""
        return self._items.get(item_id, 0) >= count

    def get_count(self, item_id: str) -> int:
        """!@brief 获取物品数量"""
        return self._items.get(item_id, 0)

    @property
    def items(self) -> dict[str, int]:
        return dict(self._items)
