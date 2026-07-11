"""!
@file core/animation.py
@brief 动画系统

提供补间动画(Tween)、缓动函数(Easing)和动画状态机。
"""

import math
from typing import Any, Callable, Optional

from core import log_manager

_logger = log_manager.get_logger('core.animation')


class Easing:
    """!@brief 缓动函数集合"""

    @staticmethod
    def linear(t):
        return t

    @staticmethod
    def ease_in_quad(t):
        return t * t

    @staticmethod
    def ease_out_quad(t):
        return t * (2 - t)

    @staticmethod
    def ease_in_out_quad(t):
        return 2 * t * t if t < 0.5 else -1 + (4 - 2 * t) * t

    @staticmethod
    def ease_in_cubic(t):
        return t * t * t

    @staticmethod
    def ease_out_cubic(t):
        t1 = t - 1
        return t1 * t1 * t1 + 1

    @staticmethod
    def ease_in_out_cubic(t):
        return 4 * t * t * t if t < 0.5 else (t - 1) * (2 * t - 2) * (2 * t - 2) + 1

    @staticmethod
    def ease_out_bounce(t):
        if t < 1 / 2.75:
            return 7.5625 * t * t
        elif t < 2 / 2.75:
            t -= 1.5 / 2.75
            return 7.5625 * t * t + 0.75
        elif t < 2.5 / 2.75:
            t -= 2.25 / 2.75
            return 7.5625 * t * t + 0.9375
        else:
            t -= 2.625 / 2.75
            return 7.5625 * t * t + 0.984375

    @staticmethod
    def ease_out_elastic(t):
        if t == 0 or t == 1:
            return t
        return 2 ** (-10 * t) * math.sin((t - 0.075) * (2 * math.pi) / 0.3) + 1


class Tween:
    """!@brief 补间动画 - 在指定时间内从起始值过渡到目标值"""

    def __init__(self, start: float, end: float, duration: float,
                 easing: Callable = None,
                 on_update: Callable = None,
                 on_complete: Callable = None):
        self.start = start
        self.end = end
        self.duration = max(0.001, duration)
        self.easing = easing or Easing.linear
        self.on_update = on_update
        self.on_complete = on_complete
        self.elapsed = 0.0
        self.finished = False
        self.value = start

    def update(self, delta_time: float) -> None:
        if self.finished:
            return
        self.elapsed += delta_time
        t = min(1.0, self.elapsed / self.duration)
        et = self.easing(t)
        self.value = self.start + (self.end - self.start) * et
        if self.on_update:
            self.on_update(self.value)
        if t >= 1.0:
            self.finished = True
            if self.on_complete:
                self.on_complete()

    def reset(self) -> None:
        self.elapsed = 0.0
        self.finished = False
        self.value = self.start


class TweenManager:
    """!@brief 补间动画管理器"""

    def __init__(self):
        self._tweens: list[Tween] = []

    def add(self, tween: Tween) -> Tween:
        self._tweens.append(tween)
        return tween

    def to(self, start: float, end: float, duration: float,
           easing: Callable = None,
           on_update: Callable = None,
           on_complete: Callable = None) -> Tween:
        tween = Tween(start, end, duration, easing, on_update, on_complete)
        return self.add(tween)

    def update(self, delta_time: float) -> None:
        for tween in self._tweens:
            tween.update(delta_time)
        self._tweens = [t for t in self._tweens if not t.finished]

    def clear(self) -> None:
        self._tweens.clear()

    @property
    def active_count(self) -> int:
        return len(self._tweens)


class AnimationState:
    """!@brief 动画状态"""

    def __init__(self, name: str, sprite_animation=None,
                 loop: bool = True, speed: float = 1.0):
        self.name = name
        self.sprite_animation = sprite_animation
        self.loop = loop
        self.speed = speed


class AnimationStateMachine:
    """!@brief 动画状态机 - 管理实体动画状态切换"""

    def __init__(self):
        self._states: dict[str, AnimationState] = {}
        self._transitions: dict[str, dict[str, Callable]] = {}
        self._current: Optional[str] = None
        self._parameters: dict[str, Any] = {}

    def add_state(self, state: AnimationState) -> None:
        self._states[state.name] = state

    def add_transition(self, from_state: str, to_state: str,
                       condition: Callable = None) -> None:
        if from_state not in self._transitions:
            self._transitions[from_state] = {}
        self._transitions[from_state][to_state] = condition

    def set_parameter(self, name: str, value: Any) -> None:
        self._parameters[name] = value

    def get_parameter(self, name: str, default: Any = None) -> Any:
        return self._parameters.get(name, default)

    def force_state(self, name: str) -> None:
        if name in self._states:
            self._current = name
            state = self._states[name]
            if state.sprite_animation:
                state.sprite_animation.reset()

    def update(self, delta_time: float) -> None:
        if self._current and self._current in self._transitions:
            for to_state, condition in self._transitions[self._current].items():
                if condition is None or condition():
                    self.force_state(to_state)
                    break

        if self._current and self._current in self._states:
            state = self._states[self._current]
            if state.sprite_animation:
                state.sprite_animation.update(delta_time * state.speed)

    @property
    def current_state(self) -> Optional[str]:
        return self._current

    @property
    def current_animation(self):
        if self._current and self._current in self._states:
            return self._states[self._current].sprite_animation
        return None
