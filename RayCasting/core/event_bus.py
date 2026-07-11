"""!
@file core/event_bus.py
@brief 事件总线模块

发布/订阅模式的事件总线，实现组件间解耦通信。
支持优先级订阅、一次性订阅、事件过滤等扩展功能。
"""

from typing import Any, Callable, Optional
from core import log_manager

_logger = log_manager.get_logger('core.event_bus')


class EventType:
    """!@brief 事件类型常量"""

    INPUT_KEY_DOWN = 'input.key_down'
    INPUT_KEY_UP = 'input.key_up'
    INPUT_MOUSE_CLICK = 'input.mouse_click'
    INPUT_MOUSE_MOVE = 'input.mouse_move'
    INPUT_ACTION = 'input.action'

    PLAYER_MOVED = 'player.moved'
    PLAYER_ROTATED = 'player.rotated'
    PLAYER_PITCH_CHANGED = 'player.pitch_changed'
    PLAYER_HEALTH_CHANGED = 'player.health_changed'
    PLAYER_DIED = 'player.died'

    GAME_STATE_CHANGE = 'game.state_change'
    GAME_EXIT_REACHED = 'game.exit_reached'
    GAME_START = 'game.start'
    GAME_PAUSE = 'game.pause'
    GAME_RESUME = 'game.resume'
    GAME_WIN = 'game.win'
    GAME_QUIT = 'game.quit'
    GAME_FRAME_BEGIN = 'game.frame_begin'
    GAME_FRAME_END = 'game.frame_end'

    WORLD_MAZE_GENERATED = 'world.maze_generated'
    WORLD_ENTITY_ADDED = 'world.entity_added'
    WORLD_ENTITY_REMOVED = 'world.entity_removed'

    RENDER_PRE_SCENE = 'render.pre_scene'
    RENDER_POST_SCENE = 'render.post_scene'
    RENDER_PRE_OUTPUT = 'render.pre_output'
    RENDER_FRAME_READY = 'render.frame_ready'

    PLUGIN_LOADED = 'plugin.loaded'
    PLUGIN_UNLOADED = 'plugin.unloaded'

    SETTING_CHANGED = 'setting.changed'

    # 动态注册机制
    _custom_types: dict = {}

    @classmethod
    def register(cls, name: str, value: str = None) -> str:
        """!@brief 注册自定义事件类型

        @param name  事件名称（如 'monster.caught'）
        @param value 事件值，默认为name本身
        @return 事件值字符串
        """
        if value is None:
            value = name
        cls._custom_types[name] = value
        return value

    @classmethod
    def get(cls, name: str) -> str:
        """!@brief 获取事件类型值，支持自定义类型"""
        upper = name.upper().replace('.', '_')
        if hasattr(cls, upper):
            return getattr(cls, upper)
        return cls._custom_types.get(name, name)


class _Subscription:
    """!@brief 订阅记录"""

    __slots__ = ('handler', 'priority', 'once', 'filter_fn')

    def __init__(self, handler: Callable, priority: int = 0,
                 once: bool = False,
                 filter_fn: Optional[Callable[[Any], bool]] = None):
        self.handler = handler
        self.priority = priority
        self.once = once
        self.filter_fn = filter_fn


class EventBus:
    """!@brief 事件总线

    提供发布/订阅机制，组件间通过事件通信而非直接方法调用。
    同步派发，handler中禁止阻塞操作。handler异常不中断其他handler。
    支持优先级、一次性订阅、事件过滤。
    """

    def __init__(self):
        self._handlers: dict[str, list[_Subscription]] = {}
        self._history: dict[str, list[Any]] = {}
        self._history_limit: int = 10

    def subscribe(self, event_type: str, handler: Callable,
                  priority: int = 0, once: bool = False,
                  filter_fn: Optional[Callable[[Any], bool]] = None) -> None:
        """!@brief 订阅事件

        @param event_type 事件类型字符串
        @param handler    回调函数，签名为 handler(data=None)
        @param priority   优先级，越小越先调用
        @param once       是否一次性订阅（触发后自动取消）
        @param filter_fn  事件过滤函数，返回True时才触发handler
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        sub = _Subscription(handler, priority, once, filter_fn)
        self._handlers[event_type].append(sub)
        self._handlers[event_type].sort(key=lambda s: s.priority)

    def subscribe_once(self, event_type: str, handler: Callable,
                       priority: int = 0) -> None:
        """!@brief 一次性订阅，触发后自动取消"""
        self.subscribe(event_type, handler, priority, once=True)

    def unsubscribe(self, event_type: str, handler: Callable) -> None:
        """!@brief 取消订阅"""
        if event_type not in self._handlers:
            return
        self._handlers[event_type] = [
            s for s in self._handlers[event_type] if s.handler != handler]

    def publish(self, event_type: str, data: Any = None) -> None:
        """!@brief 发布事件

        同步调用所有订阅该事件的handler。单个handler异常不影响其他handler。

        @param event_type 事件类型字符串
        @param data       事件数据（dict或None）
        """
        self._record_history(event_type, data)
        if event_type not in self._handlers:
            return
        to_remove = []
        for sub in self._handlers[event_type]:
            if sub.filter_fn is not None:
                try:
                    if not sub.filter_fn(data):
                        continue
                except Exception:
                    continue
            try:
                sub.handler(data)
            except Exception as e:
                _logger.error('事件处理器异常: %s, 事件: %s', e, event_type)
            if sub.once:
                to_remove.append(sub)
        for sub in to_remove:
            try:
                self._handlers[event_type].remove(sub)
            except ValueError:
                pass

    def clear(self, event_type: Optional[str] = None) -> None:
        """!@brief 清除订阅

        @param event_type 指定事件类型，为None时清除所有
        """
        if event_type is not None:
            self._handlers.pop(event_type, None)
        else:
            self._handlers.clear()

    def _record_history(self, event_type: str, data: Any) -> None:
        """!@brief 记录事件历史"""
        if event_type not in self._history:
            self._history[event_type] = []
        self._history[event_type].append(data)
        if len(self._history[event_type]) > self._history_limit:
            self._history[event_type].pop(0)

    def get_history(self, event_type: str, limit: int = 10) -> list:
        """!@brief 获取事件历史记录"""
        history = self._history.get(event_type, [])
        return history[-limit:]

    def has_subscribers(self, event_type: str) -> bool:
        """!@brief 检查是否有订阅者"""
        return bool(self._handlers.get(event_type))
