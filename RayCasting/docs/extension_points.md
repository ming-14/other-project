# 扩展点指南

本文档列出引擎中所有可扩展的接入点，以及每种扩展的标准写法。

---

## 1. 扩展点总览

| 扩展点 | 接口/基类 | 注册方式 | 用途 |
|--------|-----------|----------|------|
| 迷宫生成器 | `MazeGenerator` | `world_manager.register_generator()` | 自定义迷宫布局算法 |
| 分块生成器 | `ChunkGenerator` | `ChunkMap(generator=...)` | 自定义无限地图风格 |
| 实体组件 | `Component` | `entity.attach()` | 为实体添加行为 |
| 碰撞检测器 | `CollisionChecker` | `collision_system.register_checker()` | 自定义碰撞层 |
| 实体碰撞检测器 | `EntityCollisionChecker` | `collision_system.register_checker()` | 基于空间查询的实体碰撞 |
| 触发区域 | `TriggerZone` | `triggers.add_zone()` | 进入区域触发事件 |
| 渲染层 | 任意实现 `on_render(context)` | `render_pipeline.add_layer()` | 在场景上叠加自定义渲染 |
| 自定义视角渲染层 | 任意实现 `on_render(context)` | `render_pipeline.add_layer(priority=-100)` | 完全替换场景渲染（如第三人称俯视） |
| 后处理效果 | `PostProcessEffect` | `render_pipeline.add_post_effect()` | 屏幕空间效果 |
| UI组件 | `UIComponent` | `render_pipeline.add_ui_component()` | 叠加UI元素 |
| HUD提供者 | `Callable[[], str]` | `api.add_hud_provider()` | 在底部HUD添加信息 |
| 动作绑定 | `Callable[[bool], None]` | `api.bind_action()` | 响应输入动作 |
| 事件订阅 | `Callable[[Any], None]` | `api.subscribe()` | 响应引擎事件 |
| 设置监听 | `Callable[[str, Any, Any], None]` | `api.on_setting_change()` | 响应设置变更 |
| 光照覆盖 | — | `lighting.override_wall_color()` | 覆盖墙类型颜色 |
| 雾化函数 | `Callable[[float], float]` | `lighting.set_fog_factor_fn()` | 自定义距离雾化曲线 |
| 光线过滤 | `Callable[[RayHit], bool]` | `raycaster.add_hit_filter()` | 过滤光线命中结果 |
| 光线回调 | `Callable[[int, RayHit], None]` | `raycaster.add_on_hit()` | 每条光线命中后回调 |
| 精灵组件 | `SpriteComponent` | `entity.attach()` | 在3D场景中显示实体 |
| 精灵动画 | `SpriteAnimation` | `sprite_comp.add_animation()` | 精灵帧动画播放 |
| 相机震动 | — | `camera.trigger_shake()` | 画面震动效果 |
| 补间动画 | `Tween` | `tweens.add()` / `api.create_tween()` | 数值平滑过渡 |
| 粒子发射器 | `ParticleEmitter` | `api.add_particle_emitter()` | 粒子视觉效果 |
| 音效 | — | `audio.register_sound()` / `audio.play()` | 事件驱动音效 |
| 游戏程序 | `on_setup(engine)` | `engine.set_program()` | 完整游戏逻辑 |
| 插件 | `Plugin` | `api.register_plugin()` | 可插拔引擎扩展模块 |

---

## 2. 游戏程序

**场景**：你想创建一个全新的游戏。

```python
class MyProgram:
    def on_setup(self, engine):
        # 配置世界
        maze = Maze(seed=42)
        engine.player.x = maze.start[0]
        engine.player.y = maze.start[1]
        engine.player.set_collision_fn(maze.is_wall)
        engine.raycaster.maze = maze
        engine.render_pipeline.maze = maze
        engine.render_pipeline.scene.maze = maze

        # 注册状态
        engine.states.add_state('start', self._handle_start)
        engine.states.add_state('playing', self._handle_playing)
        engine.states.start('start')

    def _handle_start(self, clicked=None):
        # 显示开始画面...
        engine.states.transition('playing')
        return True

    def _handle_playing(self, clicked=False):
        # 游戏逻辑...
        # 引擎通用更新
        engine.camera.update(engine.delta_time)
        engine.tweens.update(engine.delta_time)
        engine.entity_manager.update_all(engine.delta_time)
        # 渲染...
        return True

# 运行
engine = Engine()
engine.set_program(MyProgram())
engine.run()
```

---

## 3. 分块无限地图生成器

**场景**：你想生成不同风格的无限地图。

```python
from world.chunk_map import ChunkGenerator

class OpenRoomGenerator(ChunkGenerator):
    @property
    def name(self) -> str:
        return 'open_room'

    def generate(self, chunk_x, chunk_y, size, rng):
        grid = [[1] * size for _ in range(size)]
        # 开挖中央大房间
        for y in range(2, size - 2):
            for x in range(2, size - 2):
                grid[y][x] = 0
        # 随机柱子
        for _ in range(size * size // 10):
            px = rng.randrange(3, size - 3)
            py = rng.randrange(3, size - 3)
            grid[py][px] = 1
        # 边界开口
        mid = size // 2
        for x in range(mid - 1, mid + 2):
            grid[0][x] = 0
            grid[size - 1][x] = 0
        return grid

# 使用
chunk_map = ChunkMap(seed=42, generator=OpenRoomGenerator())
```

---

## 4. 精灵渲染

**场景**：你想在3D场景中显示实体（金币、NPC等）。

```python
from world.entity import Entity
from world.sprite import SpriteFrame, SpriteComponent

# 纯色精灵
frame = SpriteFrame.from_color(4, 4, (255, 215, 0), 'diamond')
entity = Entity('coin', 5.0, 5.0)
entity.attach(SpriteComponent(frame, visible_distance=13.0))
entity.get_component('SpriteComponent').bob_amplitude = 0.05
entity.get_component('SpriteComponent').bob_speed = 3.0
engine.entity_manager.add(entity, 'coins')

# ASCII art精灵
frame = SpriteFrame.from_ascii(
    [' # ', '###', ' # '],
    {'#': (200, 50, 50), ' ': None}
)
entity.attach(SpriteComponent(frame))
```

---

## 5. 实体管理

**场景**：你需要高效管理大量实体。

```python
# 链式查询
coins = engine.entity_manager.query() \
    .with_tag('coin') \
    .in_radius(player.x, player.y, 5.0) \
    .execute()

# 对象池（高频创建/销毁）
engine.entity_manager.register_pool('bullet',
    lambda: Entity('', 0, 0), 50)
bullet = engine.entity_manager.spawn_from_pool('bullet', 'b_1', x, y)
engine.entity_manager.return_to_pool('bullet', 'b_1')

# 分组
engine.entity_manager.add(entity, 'enemies')
enemies = engine.entity_manager.get_group('enemies')
```

---

## 6. 碰撞扩展

**场景**：你想添加实体碰撞检测或触发区域。

```python
from world.collision_ext import EntityCollisionChecker, TriggerZone

# 实体碰撞
checker = EntityCollisionChecker(engine.entity_manager, target_tag='obstacle')
engine.world_manager.collision.register_checker('obstacle', checker)

# 触发区域
zone = TriggerZone('trap', 10.0, 10.0, 1.0, 'game.trap_triggered', {'damage': 20})
zone.one_shot = True
engine.triggers.add_zone(zone)
engine.api.subscribe('game.trap_triggered', lambda d: print(f'陷阱! 伤害:{d["damage"]}'))
```

---

## 7. 相机效果

**场景**：你想添加画面震动或FOV变化。

```python
# 震动
engine.camera.trigger_shake(intensity=0.1, duration=0.3)

# 疾跑FOV拉伸
engine.camera.set_sprint_fov(True)

# 自定义偏移（跳跃/滑行）
engine.camera.offset_pitch = 0.3
engine.camera.offset_height = -0.2
```

---

## 8. 动画系统

**场景**：你想让数值平滑过渡。

```python
from core.animation import Easing

# 补间动画
engine.api.create_tween(
    start=0.0, end=1.0, duration=0.5,
    easing=Easing.ease_out_quad,
    on_update=lambda v: print(f'进度: {v:.2f}'),
    on_complete=lambda: print('完成!')
)

# 精灵动画
from world.sprite import SpriteAnimation, SpriteFrame
frames = [SpriteFrame.from_color(3, 3, (r, 0, 0)) for r in range(0, 255, 50)]
anim = SpriteAnimation(frames, frame_duration=0.1, loop=True)
sprite_comp = entity.get_component('SpriteComponent')
sprite_comp.add_animation('pulse', anim)
sprite_comp.play('pulse')
```

---

## 9. 粒子效果

**场景**：你想添加视觉粒子效果。

```python
from world.particle import ParticleEmitter

emitter = ParticleEmitter(5.0, 5.0, config={
    'rate': 20, 'life': 0.5, 'speed': 3.0,
    'color': (255, 200, 50), 'size': 2, 'max_particles': 30
})
engine.api.add_particle_emitter(emitter)
```

---

## 10. 音频

**场景**：你想在事件触发时播放音效。

```python
engine.audio.register_sound('hit', 'sounds/hit.wav')
engine.audio.subscribe_events({
    'game.obstacle_hit': 'hit',
    'game.coin_collected': 'coin'
})
```

---

## 11. 组合扩展为插件

将引擎级扩展组合为可插拔模块：

```python
from core.engine.plugin import Plugin, PluginContext

class MyPlugin(Plugin):
    @property
    def name(self):
        return 'my_plugin'

    def on_load(self, ctx):
        ctx.renderer.add_post_effect(MyEffect())
        ctx.events.subscribe(EventType.PLAYER_MOVED, self._on_move)

    def on_unload(self, ctx):
        ctx.renderer.remove_post_effect('my_effect')
        ctx.events.unsubscribe(EventType.PLAYER_MOVED, self._on_move)
```

注意：插件用于**引擎级扩展**（渲染效果、通用工具等），游戏逻辑应放在**程序(Program)**中。

---

## 12. 自定义视角渲染层

**场景**：你想实现不同于第一人称光线投射的视角（如第三人称俯视、侧视角等）。

渲染层通过 `priority` 参数控制渲染顺序。当 priority 足够小（如 -100）时，该层会先于 SceneBuilder 执行，从而覆盖整个画面，实现完全自定义的视角渲染。

```python
class ThirdPersonRenderer:
    def __init__(self, player, maze, entity_manager):
        self._player = player
        self._maze = maze
        self._em = entity_manager

    def on_render(self, context):
        buffer = context['buffer']
        w = buffer.width
        h = buffer.pixel_height
        # 自定义渲染逻辑：填充天空、走廊、实体、玩家等
        # ...

# 注册时使用负优先级，确保在 SceneBuilder 之前执行
engine.render_pipeline.add_layer('third_person', ThirdPersonRenderer(...), priority=-100)
```

**要点**：
- `on_render(context)` 接收包含 `buffer`、`hits`、`player`、`maze`、`lighting`、`camera` 的上下文字典
- 使用 `buffer.data[row][col_start:col_end] = [packed] * span` 进行高效 slice 填充
- 像素以 int 打包存储：`(r << 16) | (g << 8) | b`
- 神庙逃亡的 `ThirdPersonRenderer` 即采用此方式实现第三人称俯视视角
