"""!
@file core/api.py
@brief 引擎公共API

提供面向插件/扩展开发者的高层API入口，
隐藏内部实现细节，仅暴露稳定的公共接口。
"""

from typing import Any, Callable, Optional, Type
from core.logging import log_manager

_logger = log_manager.get_logger('core.api')


class EngineAPI:
    """!@brief 引擎公共API

    所有对引擎的扩展操作应通过此API进行，
    而非直接访问内部模块。
    """

    def __init__(self, engine: 'Engine'):
        self._engine = engine

    # ========================================================================
    # 事件系统
    # ========================================================================

    def subscribe(self, event_type: str, handler: Callable) -> None:
        """!@brief 订阅事件

        @param event_type 事件类型字符串
        @param handler    回调函数 handler(data=None)
        """
        self._engine.events.subscribe(event_type, handler)

    def unsubscribe(self, event_type: str, handler: Callable) -> None:
        """!@brief 取消订阅事件"""
        self._engine.events.unsubscribe(event_type, handler)

    def publish(self, event_type: str, data: Any = None) -> None:
        """!@brief 发布事件"""
        self._engine.events.publish(event_type, data)

    # ========================================================================
    # 组件注册
    # ========================================================================

    def register_component(self, name: str, component: Any, *tags: str) -> None:
        """!@brief 注册组件到引擎"""
        self._engine.registry.register(name, component, *tags)

    def get_component(self, name: str) -> Optional[Any]:
        """!@brief 获取已注册组件"""
        return self._engine.registry.get(name)

    def find_components(self, tag: str) -> list:
        """!@brief 按标签查找组件"""
        return self._engine.registry.find_by_tag(tag)

    # ========================================================================
    # 世界操作
    # ========================================================================

    def get_maze(self):
        """!@brief 获取当前迷宫"""
        return self._engine.world_manager.maze

    def get_player(self):
        """!@brief 获取玩家实体"""
        return self._engine.player

    def is_wall(self, x: float, y: float) -> bool:
        """!@brief 查询指定位置是否为墙"""
        maze = self._engine.world_manager.maze or self._engine.maze
        return maze.is_wall(x, y)

    def cell_type(self, x: float, y: float) -> int:
        """!@brief 查询指定位置单元格类型"""
        maze = self._engine.world_manager.maze or self._engine.maze
        return maze.cell_type(x, y)

    # ========================================================================
    # 设置
    # ========================================================================

    def get_setting(self, group: str, key: str, default: Any = None) -> Any:
        """!@brief 获取运行时设置"""
        return self._engine.settings.get(group, key, default)

    def set_setting(self, group: str, key: str, value: Any) -> bool:
        """!@brief 设置运行时参数"""
        return self._engine.settings.set(group, key, value)

    def on_setting_change(self, group: str, key: str,
                          callback: Callable[[str, Any, Any], None]) -> None:
        """!@brief 监听设置变更"""
        self._engine.settings.on_change(group, key, callback)

    # ========================================================================
    # 渲染
    # ========================================================================

    def get_buffer(self):
        """!@brief 获取像素缓冲区"""
        return self._engine.render_pipeline.buffer

    def add_render_layer(self, name: str, layer: Any, priority: int = 0) -> None:
        """!@brief 添加渲染层

        @param name     层名称
        @param layer    实现on_render(context)的对象
        @param priority 优先级，越小越先渲染
        """
        self._engine.render_pipeline.add_layer(name, layer, priority)

    def remove_render_layer(self, name: str) -> None:
        """!@brief 移除渲染层"""
        self._engine.render_pipeline.remove_layer(name)

    # ========================================================================
    # 输入
    # ========================================================================

    def bind_action(self, action: str, handler: Callable[[bool], None]) -> None:
        """!@brief 绑定动作回调

        @param action  动作名称
        @param handler 回调 handler(pressed: bool)
        """
        self._engine.input_system.bind_action(action, handler)

    def unbind_action(self, action: str) -> None:
        """!@brief 解绑动作回调"""
        self._engine.input_system.unbind_action(action)

    # ========================================================================
    # 状态
    # ========================================================================

    def add_state(self, name: str, handler: Callable) -> None:
        """!@brief 注册游戏状态"""
        self._engine.states.add_state(name, handler)

    def transition(self, to_state: str) -> bool:
        """!@brief 请求状态转换"""
        return self._engine.states.transition(to_state)

    @property
    def current_state(self) -> str:
        """!@brief 当前游戏状态"""
        return self._engine.states.current

    # ========================================================================
    # 插件
    # ========================================================================

    def register_plugin(self, plugin: Any) -> bool:
        """!@brief 注册插件"""
        return self._engine.plugin_manager.register(plugin)

    def get_plugin(self, name: str) -> Optional[Any]:
        """!@brief 获取已加载插件"""
        return self._engine.plugin_manager.get_plugin(name)

    # ========================================================================
    # HUD
    # ========================================================================

    def add_hud_provider(self, name: str, provider: Callable[[], str]) -> None:
        """!@brief 添加HUD信息提供者

        @param name     提供者名称
        @param provider 无参回调，返回要显示的字符串
        """
        self._engine.hud.add_provider(name, provider)

    def remove_hud_provider(self, name: str) -> None:
        """!@brief 移除HUD信息提供者"""
        self._engine.hud.remove_provider(name)

    # ========================================================================
    # 日志
    # ========================================================================

    def get_logger(self, name: str):
        """!@brief 获取模块日志器"""
        return log_manager.get_logger(name)

    # ========================================================================
    # 引擎信息
    # ========================================================================

    @property
    def fps(self) -> float:
        """!@brief 当前帧率"""
        return self._engine.fps

    @property
    def is_running(self) -> bool:
        """!@brief 引擎是否运行中"""
        return self._engine.running

    # ========================================================================
    # 实体管理
    # ========================================================================

    def spawn_entity(self, entity_id: str, x: float, y: float,
                     angle: float = 0.0, group: str = None) -> Any:
        """!@brief 创建并注册实体"""
        from world.entity import Entity
        entity = Entity(entity_id, x, y, angle)
        self._engine.entity_manager.add(entity, group)
        return entity

    def destroy_entity(self, entity_id: str) -> bool:
        """!@brief 销毁实体"""
        entity = self._engine.entity_manager.remove(entity_id)
        return entity is not None

    def find_entities(self, tag: str = None, component: str = None,
                      near_x: float = None, near_y: float = None,
                      radius: float = None) -> list:
        """!@brief 链式查询实体"""
        q = self._engine.entity_manager.query()
        if tag:
            q = q.with_tag(tag)
        if component:
            q = q.with_component(component)
        if near_x is not None and near_y is not None and radius is not None:
            q = q.in_radius(near_x, near_y, radius)
        return q.execute()

    def get_entity(self, entity_id: str) -> Optional[Any]:
        """!@brief 获取实体"""
        return self._engine.entity_manager.get(entity_id)

    def get_entity_group(self, group: str) -> list:
        """!@brief 获取实体分组"""
        return self._engine.entity_manager.get_group(group)

    def register_entity_pool(self, name: str, factory: Callable,
                             initial_size: int = 10) -> None:
        """!@brief 注册实体对象池"""
        self._engine.entity_manager.register_pool(name, factory, initial_size)

    def spawn_pooled(self, pool_name: str, entity_id: str,
                     x: float, y: float, angle: float = 0.0,
                     group: str = None) -> Optional[Any]:
        """!@brief 从对象池生成实体"""
        return self._engine.entity_manager.spawn_from_pool(
            pool_name, entity_id, x, y, angle, group)

    def recycle_entity(self, pool_name: str, entity_id: str) -> None:
        """!@brief 回收实体到对象池"""
        self._engine.entity_manager.return_to_pool(pool_name, entity_id)

    # ========================================================================
    # 相机
    # ========================================================================

    def get_camera(self):
        """!@brief 获取相机系统"""
        return self._engine.camera

    def shake_camera(self, intensity: float = 0.05,
                     duration: float = 0.3) -> None:
        """!@brief 触发相机震动"""
        self._engine.camera.trigger_shake(intensity, duration)

    # ========================================================================
    # 动画
    # ========================================================================

    def create_tween(self, start: float, end: float, duration: float,
                     easing: Callable = None, on_update: Callable = None,
                     on_complete: Callable = None) -> Any:
        """!@brief 创建补间动画"""
        from core.animation import Tween, Easing
        tween = Tween(start, end, duration,
                      easing or Easing.linear, on_update, on_complete)
        self._engine.tweens.add(tween)
        return tween

    # ========================================================================
    # 碰撞
    # ========================================================================

    def register_collision_checker(self, layer: str, checker) -> None:
        """!@brief 注册碰撞检测器"""
        self._engine.world_manager.collision.register_checker(layer, checker)

    def on_collision(self, layer: str, handler: Callable) -> None:
        """!@brief 注册碰撞响应"""
        self._engine.world_manager.collision.on_collision(layer, handler)

    # ========================================================================
    # 触发区域
    # ========================================================================

    def add_trigger_zone(self, zone_id: str, x: float, y: float,
                         radius: float, event_type: str,
                         data: dict = None, one_shot: bool = True) -> None:
        """!@brief 添加触发区域"""
        from world.collision_ext import TriggerZone
        zone = TriggerZone(zone_id, x, y, radius, event_type, data)
        zone.one_shot = one_shot
        self._engine.triggers.add_zone(zone)

    def remove_trigger_zone(self, zone_id: str) -> None:
        """!@brief 移除触发区域"""
        self._engine.triggers.remove_zone(zone_id)

    # ========================================================================
    # 粒子
    # ========================================================================

    def add_particle_emitter(self, emitter) -> None:
        """!@brief 添加粒子发射器"""
        self._engine.particle_layer.add_emitter(emitter)

    def remove_particle_emitter(self, emitter) -> None:
        """!@brief 移除粒子发射器"""
        self._engine.particle_layer.remove_emitter(emitter)

    # ========================================================================
    # 音频
    # ========================================================================

    def register_sound(self, name: str, file_path: str) -> None:
        """!@brief 注册音效"""
        self._engine.audio.register_sound(name, file_path)

    def play_sound(self, name: str) -> None:
        """!@brief 播放音效"""
        self._engine.audio.play(name)

    # ========================================================================
    # 游戏模式
    # ========================================================================

    def register_game_mode(self, mode) -> None:
        """!@brief 注册游戏模式"""
        self._engine.game_modes.register(mode)

    def set_game_mode(self, name: str) -> bool:
        """!@brief 切换游戏模式"""
        return self._engine.game_modes.set_mode(name, self._engine)

    # ========================================================================
    # 地图
    # ========================================================================

    def set_chunk_map(self, chunk_map) -> None:
        """!@brief 切换为分块地图"""
        from world.chunk_map import MazeAdapter
        adapter = MazeAdapter(chunk_map)
        self._engine.raycaster.maze = adapter
        self._engine.render_pipeline.maze = adapter
        self._engine.render_pipeline.scene.maze = adapter
        self._engine.player.set_collision_fn(adapter.is_wall)
        self._engine._chunk_map = chunk_map

    def update_map_position(self, x: float, y: float) -> None:
        """!@brief 更新地图玩家位置（用于分块地图动态加载）"""
        if hasattr(self._engine, '_chunk_map') and self._engine._chunk_map:
            self._engine._chunk_map.update_player_position(x, y)
