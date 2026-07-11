"""!
@file world/camera.py
@brief 相机系统

独立于Player的视角控制，支持偏移、震动、平滑过渡。
"""

import random
from typing import Optional

from core import log_manager

_logger = log_manager.get_logger('world.camera')


class CameraShake:
    """!@brief 相机震动"""

    def __init__(self, intensity: float = 0.05, duration: float = 0.3,
                 decay: float = 0.9):
        self.base_intensity = intensity
        self.duration = duration
        self.decay = decay
        self.elapsed = 0.0
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.active = False

    def start(self, intensity: float = None, duration: float = None) -> None:
        self.active = True
        self.elapsed = 0.0
        if intensity is not None:
            self.base_intensity = intensity
        if duration is not None:
            self.duration = duration

    def update(self, delta_time: float) -> None:
        if not self.active:
            self.offset_x = 0.0
            self.offset_y = 0.0
            return
        self.elapsed += delta_time
        if self.elapsed >= self.duration:
            self.active = False
            self.offset_x = 0.0
            self.offset_y = 0.0
            return
        progress = self.elapsed / self.duration
        current_intensity = self.base_intensity * (self.decay ** (progress * 10))
        self.offset_x = random.uniform(-current_intensity, current_intensity)
        self.offset_y = random.uniform(-current_intensity, current_intensity)

    @property
    def is_shaking(self) -> bool:
        return self.active


class Camera:
    """!@brief 相机系统

    独立于Player的视角控制。
    Player只负责位置/朝向，Camera负责视角效果。
    """

    def __init__(self, player):
        self._player = player
        self.shake = CameraShake()
        self.offset_pitch = 0.0
        self.offset_height = 0.0
        self.smooth_pitch = 0.0
        self.smooth_speed = 8.0
        self.fov_multiplier = 1.0
        self.target_fov_multiplier = 1.0

    def update(self, delta_time: float) -> None:
        self.shake.update(delta_time)

        diff = self.offset_pitch - self.smooth_pitch
        self.smooth_pitch += diff * min(1.0, self.smooth_speed * delta_time)

        fov_diff = self.target_fov_multiplier - self.fov_multiplier
        self.fov_multiplier += fov_diff * min(1.0, 5.0 * delta_time)

    @property
    def effective_pitch(self) -> float:
        return self._player.pitch + self.smooth_pitch + self.shake.offset_y

    @property
    def effective_angle(self) -> float:
        return self._player.angle + self.shake.offset_x

    @property
    def effective_height(self) -> float:
        return self.offset_height

    def trigger_shake(self, intensity: float = 0.05,
                      duration: float = 0.3) -> None:
        self.shake.start(intensity, duration)

    def set_sprint_fov(self, sprinting: bool) -> None:
        self.target_fov_multiplier = 1.15 if sprinting else 1.0
