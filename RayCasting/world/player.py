"""!
@file world/player.py
@brief 玩家状态与移动控制模块

维护玩家在迷宫中的位置、朝向，并处理带碰撞检测的移动与旋转。
玩家继承自Entity，自带MovementComponent。
"""

import math
from typing import Callable, Optional

from config import MOVE_SPEED, ROTATE_SPEED, WALL_PADDING, PITCH_MAX
from core import log_manager
from world.entity import Entity, MovementComponent

_logger = log_manager.get_logger('world.player')


class Player(Entity):
    """!@brief 玩家实体

    继承Entity，内置MovementComponent。
    保持向后兼容的接口，同时支持组件式扩展。
    """

    def __init__(self, x, y, angle=0.0):
        super().__init__('player', x, y, angle)
        self._movement = MovementComponent(
            move_speed=MOVE_SPEED,
            rotate_speed=ROTATE_SPEED,
            wall_padding=WALL_PADDING,
        )
        self.attach(self._movement)
        self._on_move_callbacks: list[Callable] = []
        self._on_rotate_callbacks: list[Callable] = []

    def set_collision_fn(self, fn: Callable[[float, float], bool]) -> None:
        """!@brief 设置碰撞检测函数"""
        self._movement.set_collision_fn(fn)

    def move_forward(self, maze, distance=MOVE_SPEED):
        """!@brief 沿朝向方向前进"""
        old_x, old_y = self.x, self.y
        self._movement.move_forward(self, distance)
        if self.x != old_x or self.y != old_y:
            for cb in self._on_move_callbacks:
                cb(self.x, self.y)

    def strafe(self, maze, distance=MOVE_SPEED):
        """!@brief 左右平移（垂直于朝向）"""
        old_x, old_y = self.x, self.y
        self._movement.strafe(self, distance)
        if self.x != old_x or self.y != old_y:
            for cb in self._on_move_callbacks:
                cb(self.x, self.y)

    def rotate(self, angle_delta=ROTATE_SPEED):
        """!@brief 旋转玩家朝向"""
        self._movement.rotate(self, angle_delta)
        for cb in self._on_rotate_callbacks:
            cb(self.angle)

    def adjust_pitch(self, delta):
        """!@brief 调整俯仰角（鼠标垂直移动）"""
        self._movement.adjust_pitch(self, delta)

    @property
    def movement(self) -> MovementComponent:
        """!@brief 获取移动组件"""
        return self._movement

    def on_move(self, callback: Callable[[float, float], None]) -> None:
        """!@brief 注册移动回调"""
        self._on_move_callbacks.append(callback)

    def on_rotate(self, callback: Callable[[float], None]) -> None:
        """!@brief 注册旋转回调"""
        self._on_rotate_callbacks.append(callback)
