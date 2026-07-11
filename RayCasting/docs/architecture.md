# 架构总览

## 1. 项目简介

RayCasting 是一个在终端/控制台中运行的游戏引擎，核心采用类似 Wolfenstein 3D 的光线投射渲染方式，同时支持自定义渲染层实现不同视角。引擎以高度模块化、接口驱动为设计原则，提供插件系统、组件注册表、运行时设置、事件总线、精灵渲染、动画系统等扩展机制。

引擎本身不包含游戏逻辑，游戏以"程序(Program)"形式基于引擎开发。目前内置两个程序：**迷宫**（第一人称光线投射视角）和**神庙逃亡**（第三人称俯视固定相机视角）。

## 2. 分层架构

```
┌──────────────────────────────────────────────────────────────┐
│                    Programs (游戏程序层)                       │
│   programs/maze/          programs/temple_run/              │
│   迷宫游戏逻辑(第一人称)   神庙逃亡游戏逻辑(第三人称俯视)     │
├──────────────────────────────────────────────────────────────┤
│                      Engine (引擎主控)                        │
│  管理主循环、协调各子系统、提供公共API、程序注入接口              │
├──────────┬──────────┬──────────┬──────────┬─────────────────┤
│  Plugin   │  Core    │  World   │ Render   │   Platform      │
│  System   │  Infra   │  System  │ Pipeline │   Layer         │
│          │          │          │          │                 │
│ 插件加载  │ 事件总线  │ 迷宫生成  │ 场景构建  │ 控制台输出       │
│ 依赖解析  │ 状态机    │ 实体组件  │ 光照计算  │ ANSI/Win32      │
│ 生命周期  │ 注册表    │ 碰撞检测  │ 后处理    │ 自动选择        │
│          │ 设置管理  │ 光线投射  │ UI叠加    │                │
│          │ 公共API   │ 精灵渲染  │ 渲染层    │                │
│          │ 动画系统  │ 分块地图  │ 精灵渲染  │                │
│          │ 音频系统  │ 相机系统  │ 粒子渲染  │                │
│          │ 粒子系统  │ 世界管理  │          │                │
├──────────┴──────────┴──────────┴──────────┴─────────────────┤
│                      EventBus                                │
│              组件间解耦通信（发布/订阅）                         │
├──────────────────────────────────────────────────────────────┤
│                    LogManager (日志系统)                       │
│         统一日志管理、可配置、异步写入、Qt桥接                   │
├──────────────────────────────────────────────────────────────┤
│                      Config                                  │
│           不可变常量 (config.py) + 运行时设置 (Settings)        │
└──────────────────────────────────────────────────────────────┘
```

## 3. 目录结构

```
RayCasting/
├── main.py                          # 入口，选择程序并运行
├── config.py                        # 不可变配置常量
├── benchmark.py                     # 性能基准测试
├── log_config.json                  # 日志系统配置文件
│
├── core/                            # 核心基础设施（平台无关）
│   ├── __init__.py                  # 包导出 + log_manager向后兼容
│   ├── event_bus.py                 # 事件总线（优先级/一次性/过滤/动态注册）
│   ├── state_machine.py             # 通用状态机（进入/退出回调）
│   ├── lifecycle.py                 # 生命周期协议（Lifecycle/Updatable/Renderable）
│   ├── registry.py                  # 组件注册表（名称/类型/标签）
│   ├── settings.py                  # 运行时设置管理（分组/校验/观察者）
│   ├── hud.py                       # HUD构建（多提供者组合）
│   ├── animation.py                 # 动画系统（Tween/Easing/AnimationStateMachine）
│   ├── audio.py                     # 音频系统（事件驱动音效播放）
│   ├── engine/                      # ── 引擎主控 ──
│   │   ├── __init__.py
│   │   ├── game.py                  # Engine引擎主控类（纯引擎，不含游戏逻辑）
│   │   ├── api.py                   # 引擎公共API
│   │   └── plugin.py                # 插件系统（加载/卸载/依赖解析）
│   └── logging/                     # ── 日志系统 ──
│       ├── __init__.py
│       ├── log_manager.py           # 日志管理器（单例入口）
│       ├── log_config.py            # 日志配置数据模型
│       ├── log_handlers.py          # 日志输出目标管理
│       ├── log_async.py             # 异步日志写入
│       └── log_qt_bridge.py         # PyQt5日志桥接
│
├── world/                           # 游戏世界（平台无关）
│   ├── __init__.py
│   ├── maze.py                      # 迷宫数据结构（支持自定义生成器）
│   ├── player.py                    # 玩家实体（继承Entity，内置MovementComponent）
│   ├── raycaster.py                 # 光线投射引擎（DDA，支持命中过滤/回调）
│   ├── entity.py                    # 实体组件系统（Entity+Component）
│   ├── entity_manager.py            # 实体管理器（空间索引/对象池/链式查询/分组）
│   ├── collision.py                 # 碰撞检测系统（分层检测器/碰撞响应）
│   ├── collision_ext.py             # 碰撞扩展（实体碰撞/触发区域）
│   ├── sprite.py                    # 精灵系统（SpriteFrame/SpriteAnimation/SpriteComponent）
│   ├── camera.py                    # 相机系统（震动/平滑过渡/FOV）
│   ├── chunk_map.py                 # 分块无限地图（ChunkMap/ChunkGenerator/MazeAdapter）
│   ├── particle.py                  # 粒子系统（ParticleEmitter）
│   ├── world_manager.py             # 世界管理器（迷宫/实体/碰撞统一管理）
│   └── generators/                  # ── 迷宫生成器 ──
│       ├── __init__.py
│       ├── base.py                  # 生成器抽象基类
│       └── recursive_backtrack.py   # 递归回溯生成器
│
├── render/                          # 渲染管线（平台无关）
│   ├── __init__.py
│   ├── pipeline.py                  # 渲染管线编排（渲染层/后处理/UI/精灵/粒子）
│   ├── scene_builder.py             # 场景像素构建
│   ├── lighting.py                  # 光照/雾化（支持颜色覆盖/自定义雾化）
│   ├── buffer.py                    # 像素缓冲区（int打包像素）
│   ├── sprite_renderer.py           # 精灵渲染器（Billboard/z-buffer/画家算法）
│   ├── particle_renderer.py         # 粒子渲染层
│   ├── postprocess/                 # ── 后处理效果 ──
│   │   ├── __init__.py
│   │   └── base.py                  # PostProcessEffect基类 + 扫描线/暗角
│   └── ui/                          # ── UI组件 ──
│       ├── __init__.py
│       └── base.py                  # UIComponent基类 + 文本叠加/进度条
│
├── input/                           # 输入抽象层
│   ├── __init__.py
│   ├── base.py                      # 输入系统抽象基类（集成ActionMap）
│   └── action_map.py                # 动作映射（运行时绑定/解绑）
│
├── platform/                        # 平台适配层
│   ├── __init__.py
│   ├── base.py                      # 平台输出抽象基类
│   ├── ansi_output.py               # ANSI真彩色序列输出
│   ├── win32_output.py              # Win32直接缓冲区输出
│   ├── win32_input.py               # Win32键盘输入
│   └── win32_mouse.py               # Win32鼠标控制器
│
├── plugins/                         # ── 引擎插件 ──
│   ├── __init__.py
│   └── minimap_plugin.py            # 小地图插件（渲染层）
│
├── programs/                        # ── 游戏程序 ──
│   ├── maze/                        # 迷宫游戏
│   │   ├── __init__.py
│   │   ├── main.py                  # 迷宫程序入口
│   │   └── maze_program.py          # 迷宫游戏逻辑
│   └── temple_run/                  # 神庙逃亡游戏
│       ├── __init__.py
│       ├── main.py                  # 神庙逃亡程序入口
│   └── temple_run_program.py    # 神庙逃亡游戏逻辑（含ThirdPersonRenderer）
│
├── docs/                            # 文档
│   ├── architecture.md
│   ├── api_reference.md
│   ├── plugin_guide.md
│   ├── extension_points.md
│   └── getting_started.md
│
└── logs/                            # 日志输出目录
```

## 4. 核心设计原则

### 4.1 引擎与程序分离

引擎(Engine)是纯基础设施，不包含任何游戏逻辑。游戏以程序(Program)形式通过 `engine.set_program(program)` 注入。程序实现 `on_setup(engine)` 方法，在其中配置引擎、注册状态、初始化游戏逻辑。

### 4.2 接口驱动

所有核心功能通过抽象基类定义接口，平台/扩展通过实现接口接入：

```
core/world/render → 抽象基类 → 平台实现/程序实现
```

### 4.3 事件解耦

组件间通过 EventBus 通信，而非直接方法调用。事件类型定义在 `EventType` 类中，支持优先级、一次性订阅、事件过滤、动态注册。

### 4.4 组合优于继承

实体系统采用 Entity + Component 组合模式，通过附加不同 Component 实现不同行为，而非深层继承。

### 4.5 注册表中心化

所有组件通过 `ComponentRegistry` 注册，支持按名称、类型、标签查询，避免全局变量散落。

### 4.6 运行时可配置

不可变常量在 `config.py`，运行时可变参数通过 `SettingsManager` 管理，支持校验、观察者回调、持久化。

## 5. 数据流

### 5.1 游戏主循环

```
Engine.run()
  │
  ├─ GAME_FRAME_BEGIN 事件
  ├─ buffer.resize()
  ├─ mouse.poll_click()
  ├─ StateMachine.update()
  │   └─ 当前状态handler（由程序注册）
  │       ├─ input.poll() → 动作处理
  │       ├─ 游戏逻辑更新（程序自定义）
  │       ├─ engine.camera/tweens/triggers/entity_manager 更新
  │       ├─ raycaster.cast() → 光线投射
  │       ├─ render_pipeline.render_scene()
  │       │   ├─ scene.build() → 场景构建
  │       │   ├─ sprite_renderer → 精灵渲染
  │       │   ├─ particle_renderer → 粒子渲染
  │       │   ├─ 渲染层（含小地图等插件层）
  │       │   ├─ 后处理效果链
  │       │   ├─ UI组件绘制
  │       │   └─ post_render回调
  │       ├─ HUD构建
  │       └─ output.write_frame() → 终端输出
  ├─ gc.collect(0)
  ├─ FPS更新
  └─ GAME_FRAME_END 事件
```

### 5.2 渲染数据流

**迷宫（第一人称光线投射）**：

```
PixelBuffer (int打包: r<<16|g<<8|b)
  ↑
  ├─ SceneBuilder: 天花板/地板行填充 + 墙面逐列覆盖
  ├─ SpriteRenderer: Billboard精灵投影 + z-buffer深度遮挡
  ├─ ParticleRenderer: 粒子3D投影
  ├─ RenderLayer: 自定义渲染层（含小地图等插件层）
  ├─ PostProcessEffect: 后处理效果链
  └─ UIComponent: UI叠加
  │
  ↓
RenderPipeline.render_to_bytes()  →  ANSI序列/RLE编码
或
PlatformOutput.write_frame()      →  Win32直接缓冲区
```

**神庙逃亡（第三人称俯视）**：

```
PixelBuffer (int打包: r<<16|g<<8|b)
  ↑
  ├─ ThirdPersonRenderer (priority=-100, 覆盖整个画面)
  │   ├─ 天空背景填充
  │   ├─ 走廊透视渲染（cell级采样 + slice填充）
  │   ├─ 实体投影（金币/障碍物）
  │   ├─ 玩家角色（含跳跃/滑行动画）
  │   └─ 怪物接近指示条
  ├─ SpriteRenderer / ParticleRenderer (被覆盖)
  ├─ PostProcessEffect: 后处理效果链
  └─ UIComponent: UI叠加
  │
  ↓
RenderPipeline.render_to_bytes()  →  ANSI序列/RLE编码
或
PlatformOutput.write_frame()      →  Win32直接缓冲区
```

## 6. 程序接口

程序(Program)是实现 `on_setup(engine)` 方法的对象，在安装时配置引擎并注册游戏状态：

```python
class MyProgram:
    def on_setup(self, engine):
        # 1. 配置世界（迷宫/分块地图等）
        # 2. 设置玩家初始位置
        # 3. 注册游戏状态（start/playing/paused/won等）
        # 4. 绑定输入动作
        # 5. 注册HUD
        # 6. 加载插件
        engine.states.start('start')
```

运行：

```python
engine = Engine()
engine.set_program(MyProgram())
engine.run()
```

## 7. 依赖规则

### 7.1 模块间依赖

```
main.py → programs/maze 或 programs/temple_run
programs/ → core.engine.game, world, render, plugins
core/         → core.logging, config.py（不依赖其他层）
core.engine/  → core.event_bus, core.state_machine, core.registry, core.settings, core.hud, core.logging, core.animation, core.audio
core.logging/ → config.py（独立，不依赖core其他模块）
world/        → config.py, core.logging（不依赖 render/input/platform）
render/       → config.py, world.maze, world.raycaster, core.logging
input/        → config.py, core.logging（不依赖 world/render/platform）
platform/     → config.py, input.base, core.logging
```

### 7.2 向后兼容

`from core import log_manager` 仍然有效（通过 `core/__init__.py` 重导出），但推荐使用新路径：

| 旧路径 | 新路径 |
|--------|--------|
| `from core import log_manager` | `from core.logging import log_manager` |
| `from core.game import Engine` | `from core.engine.game import Engine` |
| `from core.plugin import Plugin` | `from core.engine.plugin import Plugin` |
| `from core.api import EngineAPI` | `from core.engine.api import EngineAPI` |

**核心约束**：`core/`、`world/`、`render/` 中禁止直接调用平台 API，必须通过 `input/base.py` 或 `platform/base.py` 的抽象接口访问。

## 8. 性能优化

| 优化项 | 方法 | 效果 |
|--------|------|------|
| int像素打包 | `r<<16\|g<<8\|b` 替代 tuple | 场景构建 -37%，内存 -38% |
| ANSI序列缓存 | dict缓存颜色→bytes | ANSI编码 -63% |
| 行颜色缓存 | horizon不变时跳过重算 | 场景构建 -49% |
| 帧内禁GC | `gc.disable()` + 帧间 `gc.collect(0)` | P99尖峰 -50% |
| RGB→attr LUT | 6×6×6预计算查找表 | bypass_ansi加速 |
| RLE游程编码 | 连续相同像素合并 | IO数据量减少 |
| 空间哈希网格 | SpatialGrid加速范围查询 | O(n)→O(1)平均 |
| 实体对象池 | EntityPool复用实体 | 减少GC压力 |
