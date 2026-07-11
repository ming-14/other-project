# 快速上手

## 1. 运行游戏

```bash
cd RayCasting

# 迷宫
python main.py

# 神庙逃亡
python main.py temple_run
```

### 迷宫操作

| 按键 | 功能 |
|------|------|
| W / ↑ | 前进 |
| S / ↓ | 后退 |
| A | 左平移 |
| D | 右平移 |
| ← | 左转 |
| → | 右转 |
| Shift | 疾跑 |
| 鼠标左键 | 锁定/解锁鼠标视角 |
| ESC | 暂停 |

**目标**：找到绿色出口即可获胜。

### 神庙逃亡操作

| 按键 | 功能 |
|------|------|
| A / ← | 在路口左转 |
| D / → | 在路口右转 |
| W / ↑ | 跳跃 |
| S / ↓ | 滑行 |
| ESC | 暂停 |

**视角**：第三人称俯视固定相机，玩家角色在画面下方，走廊向上延伸。

**目标**：躲避障碍，收集金币，跑得越远越好。

## 2. 项目结构

```
core/       → 引擎核心（事件/状态/插件/API/注册表/设置/日志/动画/音频）
world/      → 游戏世界（迷宫/实体/碰撞/光线投射/精灵/相机/分块地图/粒子）
render/     → 渲染管线（场景/光照/精灵渲染/粒子渲染/后处理/UI/缓冲区）
input/      → 输入抽象（键盘/鼠标/动作映射）
platform/   → 平台适配（Win32输入输出/ANSI输出）
plugins/    → 引擎插件（小地图等）
programs/   → 游戏程序（迷宫/神庙逃亡）
```

## 3. 编写游戏程序

### 3.1 最简程序

```python
# programs/my_game/my_program.py
from core.engine.game import Engine

class MyProgram:
    def on_setup(self, engine: Engine):
        engine.states.add_state('playing', self._handle_playing)
        engine.states.start('playing')

    def _handle_playing(self, clicked=False):
        # 游戏逻辑...
        return True

# programs/my_game/main.py
from core.engine.game import Engine
from programs.my_game.my_program import MyProgram

def main():
    engine = Engine()
    engine.set_program(MyProgram())
    engine.run()
```

### 3.2 使用迷宫世界

```python
from world.maze import Maze
from world.raycaster import Raycaster
from render.pipeline import RenderPipeline

class MazeProgram:
    def on_setup(self, engine):
        maze = Maze(seed=42)
        engine.player.x = maze.start[0]
        engine.player.y = maze.start[1]
        engine.player.set_collision_fn(maze.is_wall)
        engine.raycaster.maze = maze
        engine.render_pipeline.maze = maze
        engine.render_pipeline.scene.maze = maze
        engine.registry.register('maze', maze, 'world')
        # 注册状态...
```

### 3.3 使用分块无限地图

```python
from world.chunk_map import ChunkMap, CorridorChunkGenerator, MazeAdapter

class InfiniteProgram:
    def on_setup(self, engine):
        chunk_map = ChunkMap(seed=42, generator=CorridorChunkGenerator())
        adapter = MazeAdapter(chunk_map)
        engine.player.x = chunk_map.start[0]
        engine.player.y = chunk_map.start[1]
        engine.player.set_collision_fn(adapter.is_wall)
        engine.raycaster.maze = adapter
        engine.render_pipeline.maze = adapter
        engine.render_pipeline.scene.maze = adapter
        # 注册状态...
```

### 3.4 使用精灵

```python
from world.entity import Entity
from world.sprite import SpriteFrame, SpriteComponent

coin = Entity('coin_1', 5.0, 5.0)
frame = SpriteFrame.from_color(3, 3, (255, 215, 0), 'diamond')
coin.attach(SpriteComponent(frame, visible_distance=13.0))
engine.entity_manager.add(coin, 'coins')
```

### 3.5 使用相机震动

```python
engine.camera.trigger_shake(intensity=0.08, duration=0.3)
```

### 3.6 使用动画

```python
engine.api.create_tween(
    start=0.0, end=1.0, duration=0.5,
    easing=Easing.ease_out_quad,
    on_update=lambda v: setattr(entity, 'x', v)
)
```

### 3.7 使用自定义视角渲染层

```python
class ThirdPersonRenderer:
    def __init__(self, player, maze):
        self._player = player
        self._maze = maze

    def on_render(self, context):
        buffer = context['buffer']
        # 自定义渲染逻辑...

# 注册时使用负优先级覆盖 SceneBuilder
engine.render_pipeline.add_layer('third_person', ThirdPersonRenderer(...), priority=-100)
```

## 4. 配置

### 4.1 不可变常量 (config.py)

```python
MAZE_WIDTH = 21          # 迷宫宽度（奇数）
MAZE_HEIGHT = 21         # 迷宫高度（奇数）
FOV = math.radians(90)   # 视野角度
MOVE_SPEED = 0.06        # 移动速度
TARGET_FPS = 30          # 目标帧率
RENDER_STRATEGY = 'ansi' # 渲染策略: ansi/quantize/bypass_ansi
FOG_NEAR = 1.2           # 雾化起始距离
FOG_FAR = 13.0           # 雾化终止距离
```

### 4.2 渲染策略

| 策略 | 说明 | 适用场景 |
|------|------|----------|
| `ansi` | ANSI 24位真彩色 + RLE | 默认，色彩最丰富 |
| `quantize` | 量化颜色 + ANSI + RLE | 慢终端，牺牲色彩换IO压缩 |
| `bypass_ansi` | Win32直接缓冲区输出 | 仅cmd，16色 |

### 4.3 日志配置

编辑 `log_config.json`：

```json
{
    "global_level": "WARNING",
    "module_levels": {
        "core.game": "INFO"
    },
    "handlers": [
        {"type": "console", "level": "WARNING"},
        {"type": "file", "level": "DEBUG", "filepath": "logs/game.log"}
    ]
}
```

## 5. 性能测试

```bash
python benchmark.py
```

## 6. 详细文档

- [架构总览](architecture.md)
- [API参考手册](api_reference.md)
- [插件开发指南](plugin_guide.md)
- [扩展点指南](extension_points.md)
