# API 参考手册

## 1. EngineAPI

引擎公共API，通过 `engine.api` 访问。所有对引擎的扩展操作应通过此API进行。

### 1.1 事件系统

```python
api.subscribe(event_type: str, handler: Callable, priority=0, once=False, filter_fn=None)
api.unsubscribe(event_type: str, handler: Callable)
api.publish(event_type: str, data=None)
```

**参数说明**：

| 参数 | 类型 | 说明 |
|------|------|------|
| `event_type` | `str` | 事件类型，使用 `EventType` 常量或动态注册值 |
| `handler` | `Callable` | 回调函数，签名 `handler(data=None)` |
| `priority` | `int` | 优先级，越小越先调用，默认0 |
| `once` | `bool` | 是否一次性订阅，触发后自动取消 |
| `filter_fn` | `Callable` | 过滤函数，返回True时才触发handler |

### 1.2 组件注册

```python
api.register_component(name: str, component: Any, *tags: str)
api.get_component(name: str) -> Optional[Any]
api.find_components(tag: str) -> list
```

### 1.3 世界操作

```python
api.get_maze() -> Maze
api.get_player() -> Player
api.is_wall(x: float, y: float) -> bool
api.cell_type(x: float, y: float) -> int
```

### 1.4 设置

```python
api.get_setting(group: str, key: str, default=None) -> Any
api.set_setting(group: str, key: str, value: Any) -> bool
api.on_setting_change(group: str, key: str, callback: Callable)
```

**回调签名**：`callback(key: str, old_value, new_value)`

### 1.5 渲染

```python
api.get_buffer() -> PixelBuffer
api.add_render_layer(name: str, layer: Any, priority: int = 0)
api.remove_render_layer(name: str)
```

**渲染层对象**需实现 `on_render(context: dict)` 方法。

### 1.6 输入

```python
api.bind_action(action: str, handler: Callable[[bool], None])
api.unbind_action(action: str)
```

### 1.7 状态

```python
api.add_state(name: str, handler: Callable)
api.transition(to_state: str) -> bool
api.current_state -> str
```

### 1.8 插件

```python
api.register_plugin(plugin: Plugin) -> bool
api.get_plugin(name: str) -> Optional[Plugin]
```

### 1.9 HUD

```python
api.add_hud_provider(name: str, provider: Callable[[], str], priority=0)
api.remove_hud_provider(name: str)
```

### 1.10 日志

```python
api.get_logger(name: str) -> logging.Logger
```

### 1.11 引擎信息

```python
api.fps -> float          # 当前帧率
api.is_running -> bool    # 引擎是否运行中
```

### 1.12 实体管理

```python
api.spawn_entity(entity_id: str, x: float, y: float, angle: float = 0.0, group: str = None) -> Entity
api.destroy_entity(entity_id: str) -> bool
api.find_entities(tag: str = None, component: str = None, near_x: float = None, near_y: float = None, radius: float = None) -> list
api.get_entity(entity_id: str) -> Optional[Entity]
api.get_entity_group(group: str) -> list
api.register_entity_pool(name: str, factory: Callable, initial_size: int = 10)
api.spawn_pooled(pool_name: str, entity_id: str, x: float, y: float, angle: float = 0.0, group: str = None) -> Optional[Entity]
api.recycle_entity(pool_name: str, entity_id: str)
```

### 1.13 相机

```python
api.get_camera() -> Camera
api.shake_camera(intensity: float = 0.05, duration: float = 0.3)
```

### 1.14 动画

```python
api.create_tween(start: float, end: float, duration: float, easing: Callable = None, on_update: Callable = None, on_complete: Callable = None) -> Tween
```

### 1.15 碰撞

```python
api.register_collision_checker(layer: str, checker: CollisionChecker)
api.on_collision(layer: str, handler: Callable[[CollisionResult], None])
```

### 1.16 触发区域

```python
api.add_trigger_zone(zone_id: str, x: float, y: float, radius: float, event_type: str, data: dict = None, one_shot: bool = True)
api.remove_trigger_zone(zone_id: str)
```

### 1.17 粒子

```python
api.add_particle_emitter(emitter: ParticleEmitter)
api.remove_particle_emitter(emitter: ParticleEmitter)
```

### 1.18 音频

```python
api.register_sound(name: str, file_path: str)
api.play_sound(name: str)
```

### 1.19 地图

```python
api.set_chunk_map(chunk_map: ChunkMap)
api.update_map_position(x: float, y: float)
```

---

## 2. EventType 事件类型

| 常量 | 值 | 数据 | 产生者 |
|------|----|------|--------|
| `INPUT_KEY_DOWN` | `input.key_down` | `{action: str}` | InputSystem |
| `INPUT_KEY_UP` | `input.key_up` | `{action: str}` | InputSystem |
| `INPUT_MOUSE_CLICK` | `input.mouse_click` | `{button: str}` | MouseInput |
| `INPUT_MOUSE_MOVE` | `input.mouse_move` | `{dx, dy}` | MouseInput |
| `INPUT_ACTION` | `input.action` | `{action, pressed}` | ActionMap |
| `PLAYER_MOVED` | `player.moved` | `{x, y}` | Player |
| `PLAYER_ROTATED` | `player.rotated` | `{angle}` | Player |
| `PLAYER_PITCH_CHANGED` | `player.pitch_changed` | `{pitch}` | Player |
| `PLAYER_HEALTH_CHANGED` | `player.health_changed` | `{health, max_health}` | HealthComponent |
| `PLAYER_DIED` | `player.died` | `{x, y}` | HealthComponent |
| `GAME_STATE_CHANGE` | `game.state_change` | `{from, to}` | StateMachine |
| `GAME_EXIT_REACHED` | `game.exit_reached` | `{x, y}` | Game |
| `GAME_START` | `game.start` | `None` | Engine |
| `GAME_PAUSE` | `game.pause` | `None` | Engine |
| `GAME_RESUME` | `game.resume` | `None` | Engine |
| `GAME_WIN` | `game.win` | `None` | Engine |
| `GAME_QUIT` | `game.quit` | `None` | Engine |
| `GAME_FRAME_BEGIN` | `game.frame_begin` | `None` | Engine |
| `GAME_FRAME_END` | `game.frame_end` | `{delta_time, fps}` | Engine |
| `WORLD_MAZE_GENERATED` | `world.maze_generated` | `{width, height, seed}` | WorldManager |
| `WORLD_ENTITY_ADDED` | `world.entity_added` | `{entity}` | WorldManager |
| `WORLD_ENTITY_REMOVED` | `world.entity_removed` | `{entity_id}` | WorldManager |
| `RENDER_PRE_SCENE` | `render.pre_scene` | `{buffer, hits, player}` | RenderPipeline |
| `RENDER_POST_SCENE` | `render.post_scene` | `{buffer, hits, player}` | RenderPipeline |
| `RENDER_PRE_OUTPUT` | `render.pre_output` | `{buffer}` | RenderPipeline |
| `RENDER_FRAME_READY` | `render.frame_ready` | `{buffer, width, height}` | RenderPipeline |
| `PLUGIN_LOADED` | `plugin.loaded` | `{name}` | PluginManager |
| `PLUGIN_UNLOADED` | `plugin.unloaded` | `{name}` | PluginManager |
| `SETTING_CHANGED` | `setting.changed` | `{group, key, old, new}` | SettingsManager |

### 动态事件注册

```python
EventType.register(name: str, value: str = None) -> str
EventType.get(name: str) -> str
```

程序可注册自定义事件类型，例如 `EventType.register('game.monster_caught')`。

---

## 3. Entity 实体系统

### 3.1 Entity

```python
entity = Entity(entity_id: str, x=0.0, y=0.0, angle=0.0)
```

| 方法/属性 | 说明 |
|-----------|------|
| `attach(component)` | 附加组件 |
| `detach(type_name)` | 分离组件，返回组件或None |
| `get_component(type_name)` | 获取组件 |
| `has_component(type_name)` | 是否拥有组件 |
| `add_tag(tag)` | 添加标签 |
| `has_tag(tag)` | 是否拥有标签 |
| `set_property(key, value)` | 设置自定义属性 |
| `get_property(key, default)` | 获取自定义属性 |
| `update(delta_time)` | 更新所有组件 |
| `dir_vector` | 朝向单位向量 `(cos, sin)` |
| `plane_vector` | 相机平面向量 |
| `components` | 所有组件列表 |

### 3.2 内置组件

**MovementComponent**

```python
mc = MovementComponent(move_speed=0.06, rotate_speed=0.045, wall_padding=0.2, sprint_multiplier=1.8)
mc.set_collision_fn(fn)
mc.move_forward(entity, dist)
mc.strafe(entity, dist)
mc.rotate(entity, delta)
mc.adjust_pitch(entity, delta)
mc.is_sprinting = True
```

**HealthComponent**

```python
hp = HealthComponent(max_health=100)
hp.take_damage(amount)
hp.heal(amount)
hp.on_death(callback)
hp.health / hp.alive
```

**InventoryComponent**

```python
inv = InventoryComponent(capacity=20)
inv.add_item(item_id, count)
inv.remove_item(item_id, count)
inv.has_item(item_id, count)
inv.get_count(item_id)
inv.items
```

**SpriteComponent**

```python
sc = SpriteComponent(frame: SpriteFrame = None, visible_distance: float = 15.0)
sc.billboard = True          # 是否始终面向相机
sc.scale = 1.0               # 缩放
sc.vertical_offset = 0.0     # 垂直偏移
sc.bob_amplitude = 0.0       # 浮动振幅
sc.bob_speed = 0.0            # 浮动速度
sc.add_animation(name, animation)
sc.play(name, reset=True)
sc.stop_animation()
sc.current_frame -> SpriteFrame
sc.current_bob_offset -> float
```

---

## 4. EntityManager 实体管理器

```python
em = engine.entity_manager

em.add(entity, group=None)              # 添加实体
em.remove(entity_id) -> Optional[Entity] # 移除实体
em.get(entity_id) -> Optional[Entity]    # 获取实体
em.query() -> EntityQuery                # 链式查询
em.query_radius(x, y, radius) -> list   # 空间查询
em.get_group(group) -> list              # 获取分组
em.update_all(delta_time)                # 更新所有实体
em.register_pool(name, factory, size)    # 注册对象池
em.spawn_from_pool(pool_name, id, x, y, angle, group) -> Entity
em.return_to_pool(pool_name, entity_id)
em.clear()
```

### EntityQuery 链式查询

```python
em.query().with_tag('coin').in_radius(px, py, 5.0).execute() -> list
em.query().with_component('SpriteComponent').first() -> Optional[Entity]
em.query().with_tag('obstacle').count() -> int
```

---

## 5. Sprite 精灵系统

### SpriteFrame

```python
frame = SpriteFrame(width, height, pixels=None, offset_x=0.0, offset_y=0.0)

SpriteFrame.from_color(width, height, color, shape='rect')   # shape: rect/diamond/circle
SpriteFrame.from_ascii(art: list[str], color_map: dict)
```

### SpriteAnimation

```python
anim = SpriteAnimation(frames: list[SpriteFrame], frame_duration=0.1, loop=True)
anim.update(delta_time)
anim.current -> SpriteFrame
anim.reset()
```

---

## 6. Camera 相机系统

```python
camera = engine.camera

camera.trigger_shake(intensity=0.05, duration=0.3)
camera.set_sprint_fov(sprinting: bool)
camera.offset_pitch = 0.0       # 额外俯仰偏移
camera.offset_height = 0.0      # 高度偏移
camera.effective_pitch -> float  # 综合俯仰角
camera.effective_angle -> float  # 综合朝向角
camera.update(delta_time)
```

---

## 7. CollisionSystem 碰撞系统

```python
cs = CollisionSystem()
cs.register_checker(layer, checker)
cs.unregister_checker(layer)
cs.check_point(x, y, layers=None)
cs.check_circle(x, y, radius, layers)
cs.on_collision(layer, handler)
```

### EntityCollisionChecker

```python
ecc = EntityCollisionChecker(entity_manager, target_tag=None, target_component=None, collision_radius=0.5)
```

### TriggerZone / TriggerSystem

```python
zone = TriggerZone(zone_id, x, y, radius, event_type, data=None)
zone.one_shot = True
zone.cooldown = 0.0

ts = engine.triggers
ts.add_zone(zone)
ts.remove_zone(zone_id)
ts.update(player_x, player_y, delta_time)
```

---

## 8. ChunkMap 分块无限地图

```python
cm = ChunkMap(chunk_size=21, seed=42, generator=CorridorChunkGenerator())
cm.is_wall(x, y) -> bool
cm.cell_type(x, y) -> int
cm.is_exit(x, y) -> bool
cm.set_cell(x, y, value)
cm.update_player_position(x, y)
cm.start -> tuple
cm.chunk_count -> int
```

### MazeAdapter

```python
adapter = MazeAdapter(chunk_map)
# 兼容Maze接口，可直接赋值给 raycaster.maze / render_pipeline.maze
```

---

## 9. Animation 动画系统

### Tween / TweenManager

```python
tween = Tween(start, end, duration, easing=Easing.linear, on_update=None, on_complete=None)
tween.update(delta_time)
tween.value -> float
tween.finished -> bool

tm = engine.tweens
tm.to(start, end, duration, ...) -> Tween
tm.update(delta_time)
```

### Easing 缓动函数

`Easing.linear` / `ease_in_quad` / `ease_out_quad` / `ease_in_out_quad` / `ease_in_cubic` / `ease_out_cubic` / `ease_in_out_cubic` / `ease_out_bounce` / `ease_out_elastic`

---

## 10. Particle 粒子系统

```python
emitter = ParticleEmitter(x, y, config={
    'rate': 10, 'life': 1.0, 'speed': 2.0, 'speed_var': 1.0,
    'angle': 0.0, 'angle_spread': math.pi*2,
    'color': (255, 200, 50), 'size': 2, 'gravity': 0.0,
    'max_particles': 50
})
emitter.emit(count=1)
emitter.update(delta_time)
emitter.particles -> list[Particle]
```

---

## 11. Audio 音频系统

```python
audio = engine.audio
audio.register_sound(name, file_path)
audio.play(name)
audio.subscribe_events(event_map: dict)  # {event_type: sound_name}
audio.set_enabled(enabled: bool)
```

---

## 12. RenderPipeline 渲染管线

```python
rp = render_pipeline

rp.add_layer(name, renderable, priority=0)
rp.remove_layer(name)
rp.add_post_effect(effect)
rp.remove_post_effect(name)
rp.add_ui_component(component)
rp.remove_ui_component(name)
rp.on_pre_render(callback)
rp.on_post_render(callback)

**渲染层优先级说明**：
- `priority < 0`：在 SceneBuilder 之前执行，可覆盖整个画面（用于自定义视角，如第三人称俯视）
- `priority = 0`（默认）：与 SceneBuilder 同级
- `priority > 0`：在 SceneBuilder 之后执行（用于叠加效果，如小地图）
rp.render_scene(hits, player, camera=None)
rp.render_to_bytes(hud_text='') -> bytes
rp.render_message(message) -> str
```

---

## 13. PostProcessEffect 后处理

```python
class MyEffect(PostProcessEffect):
    @property
    def name(self) -> str: ...
    @property
    def priority(self) -> int: ...

    def apply(self, buffer, context) -> None:
        pass
```

内置效果：`ScanlineEffect(intensity, gap)`、`VignetteEffect(strength, radius)`

---

## 14. SettingsManager 设置管理

```python
sm = get_settings()

group = sm.group('gameplay')
group.define(key, default, validator=None)
group.get(key, default=None)
group.set(key, value) -> bool
group.on_change(key, callback)
group.reset(key)
group.reset_all()

sm.get(group, key, default)
sm.set(group, key, value) -> bool
sm.on_change(group, key, callback)
sm.save_to_file(filepath) -> bool
sm.load_from_file(filepath) -> bool
```

---

## 15. ComponentRegistry 组件注册表

```python
reg = get_registry()

reg.register(name, component, *tags)
reg.unregister(name)
reg.get(name) -> Optional[Any]
reg.get_typed(name, type) -> Optional[T]
reg.find_by_type(type) -> list
reg.find_by_tag(tag) -> list
reg.find_one_by_tag(tag) -> Optional[Any]
reg.has(name) -> bool
reg.names -> list[str]
reg.count -> int
```

**默认注册组件**：

| 名称 | 类型 | 标签 |
|------|------|------|
| `engine` | `Engine` | `core` |
| `events` | `EventBus` | `core` |
| `player` | `Player` | `world` |
| `raycaster` | `Raycaster` | `world` |
| `lighting` | `Lighting` | `render` |
| `render_pipeline` | `RenderPipeline` | `render` |
| `input_system` | `InputSystem` | `input` |
| `mouse` | `MouseInput` | `input` |
| `output` | `PlatformOutput` | `platform` |
| `hud` | `HUD` | `ui` |
| `world_manager` | `WorldManager` | `world` |
| `entity_manager` | `EntityManager` | `world` |
| `camera` | `Camera` | `world` |
| `tweens` | `TweenManager` | `core` |
| `audio` | `AudioSystem` | `core` |
| `triggers` | `TriggerSystem` | `world` |

---

## 16. Lighting 光照

```python
lighting = engine.lighting

lighting.override_wall_color(wall_type, (r, g, b))
lighting.remove_wall_color_override(wall_type)
lighting.set_fog_factor_fn(fn)
lighting.get_wall_base_color(hit)
lighting.compute_fog(distance)
lighting.fog_factor(distance)
lighting.wall_color(hit, vertical_t)
lighting.ceiling_color(y, horizon, h)
lighting.floor_color(y, horizon, h)
```

---

## 17. Raycaster 光线投射

```python
rc = engine.raycaster

rc.add_hit_filter(filter_fn)
rc.add_on_hit(callback)
rc.set_max_steps(max_steps)
rc.cast(px, py, dx, dy, plx, ply, w)
```

**RayHit** 字段：`distance`、`side`(0=南北/1=东西)、`wall_type`(0/1/2)、`wall_x`(0~1)

---

## 18. MazeGenerator 迷宫生成器

```python
class MyGenerator(MazeGenerator):
    @property
    def name(self) -> str: ...

    def generate(self, width, height, seed=None) -> list[list[int]]:
        width, height = self.validate_size(width, height)
        ...
```

注册到世界管理器：

```python
engine.world_manager.register_generator(MyGenerator())
engine.world_manager.set_generator('my_gen')
```

---

## 19. ChunkGenerator 分块生成器

```python
class MyChunkGenerator(ChunkGenerator):
    @property
    def name(self) -> str: ...

    def generate(self, chunk_x, chunk_y, size, rng) -> list[list[int]]:
        ...
```

内置：`CorridorChunkGenerator`（走廊风格无限地图）
