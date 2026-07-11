# 插件开发指南

## 1. 概述

RayCasting 引擎的插件系统用于**引擎级扩展**（渲染效果、通用工具、调试辅助等）。游戏逻辑应放在**程序(Program)**中，而非插件中。

插件可以：

- 添加渲染层、后处理效果、UI组件
- 订阅/发布事件
- 修改运行时设置
- 添加HUD信息
- 绑定自定义输入动作

## 2. 最简插件

```python
from core.engine.plugin import Plugin, PluginContext

class HelloPlugin(Plugin):
    @property
    def name(self) -> str:
        return 'hello'

    def on_load(self, ctx: PluginContext) -> None:
        ctx.engine.api.get_logger('hello').info('Hello插件已加载!')

    def on_unload(self, ctx: PluginContext) -> None:
        pass
```

加载插件（在程序的 `on_setup` 中）：

```python
engine.load_plugin(HelloPlugin())
```

## 3. Plugin 接口

```python
class Plugin(ABC):
    @property
    def name(self) -> str                    # 必须实现：插件唯一标识名
    @property
    def version(self) -> str                 # 可选覆盖：版本号，默认'1.0.0'
    @property
    def description(self) -> str             # 可选覆盖：描述
    @property
    def dependencies(self) -> list[str]      # 可选覆盖：依赖的其他插件名列表

    def on_load(self, ctx: PluginContext)     # 必须实现：加载时调用
    def on_unload(self, ctx: PluginContext)   # 必须实现：卸载时调用
    def on_enable(self) -> None               # 可选覆盖：启用时调用
    def on_disable(self) -> None              # 可选覆盖：禁用时调用
```

## 4. PluginContext

插件通过 `PluginContext` 访问引擎核心API：

| 属性 | 类型 | 说明 |
|------|------|------|
| `engine` | `Engine` | 引擎实例 |
| `events` | `EventBus` | 事件总线 |
| `registry` | `ComponentRegistry` | 组件注册表 |
| `settings` | `SettingsManager` | 设置管理器 |
| `world` | `WorldManager` | 世界管理器 |
| `renderer` | `RenderPipeline` | 渲染管线 |
| `input_system` | `InputSystem` | 输入系统 |
| `player` | `Player` | 玩家实体 |

便捷方法：

| 方法 | 说明 |
|------|------|
| `get_plugin(name)` | 获取已加载的其他插件实例 |

## 5. 完整示例：小地图插件

```python
from core.engine.plugin import Plugin, PluginContext
from core.event_bus import EventType

class MinimapPlugin(Plugin):
    @property
    def name(self) -> str:
        return 'minimap'

    @property
    def description(self) -> str:
        return '左上角迷宫小地图'

    def on_load(self, ctx: PluginContext) -> None:
        self._ctx = ctx
        self._layer = MinimapLayer()
        ctx.renderer.add_layer('minimap', self._layer, priority=10)
        ctx.events.subscribe(EventType.WORLD_MAZE_GENERATED, self._on_maze_generated)
        ctx.engine.api.bind_action('minimap_toggle', self._on_toggle)

    def on_unload(self, ctx: PluginContext) -> None:
        ctx.renderer.remove_layer('minimap')
        ctx.events.unsubscribe(EventType.WORLD_MAZE_GENERATED, self._on_maze_generated)
        ctx.engine.api.unbind_action('minimap_toggle')

    def _on_maze_generated(self, data):
        maze = ctx.engine.world_manager.maze
        self._layer.set_maze(maze)

    def _on_toggle(self, pressed):
        if pressed:
            self._layer.toggle()
```

## 6. 完整示例：后处理效果插件

```python
from core.engine.plugin import Plugin, PluginContext
from render.postprocess.base import PostProcessEffect

class NightVisionEffect(PostProcessEffect):
    @property
    def name(self) -> str:
        return 'night_vision'

    @property
    def priority(self) -> int:
        return 150

    def apply(self, buffer, context):
        if not self._enabled:
            return
        for y in range(buffer.pixel_height):
            row = buffer.data[y]
            for x in range(buffer.width):
                pixel = row[x]
                r = (pixel >> 16) & 0xFF
                g = (pixel >> 8) & 0xFF
                b = pixel & 0xFF
                g = min(255, int(g * 1.3))
                r = int(r * 0.5)
                b = int(b * 0.5)
                row[x] = (r << 16) | (g << 8) | b


class NightVisionPlugin(Plugin):
    @property
    def name(self) -> str:
        return 'night_vision'

    def on_load(self, ctx: PluginContext) -> None:
        self._effect = NightVisionEffect()
        ctx.renderer.add_post_effect(self._effect)

    def on_unload(self, ctx: PluginContext) -> None:
        ctx.renderer.remove_post_effect('night_vision')
```

## 7. 插件 vs 程序

| 维度 | 插件 (Plugin) | 程序 (Program) |
|------|---------------|----------------|
| 定位 | 引擎级扩展 | 完整游戏 |
| 注册方式 | `engine.load_plugin()` | `engine.set_program()` |
| 包含游戏逻辑 | 否 | 是 |
| 包含游戏状态 | 否 | 是 |
| 可多个共存 | 是 | 同一时间只有一个 |
| 示例 | 小地图、后处理效果 | 迷宫、神庙逃亡 |

**原则**：插件提供通用能力，程序实现具体游戏。

## 8. 插件依赖

```python
class CombatPlugin(Plugin):
    @property
    def dependencies(self) -> list[str]:
        return ['night_vision']

    def on_load(self, ctx: PluginContext) -> None:
        night_vision = ctx.get_plugin('night_vision')
```

## 9. 插件生命周期

```
register → load → [enable ⇄ disable] → unload
                 ↑                        ↓
               on_load                  on_unload
```

## 10. 最佳实践

1. **在 `on_load` 中注册，在 `on_unload` 中清理** — 确保插件卸载后不留残留
2. **通过 `ctx.engine.api` 操作引擎** — 不要直接访问引擎内部属性
3. **事件订阅必须配对取消** — `on_load` 中 subscribe，`on_unload` 中 unsubscribe
4. **使用日志而非 print** — `ctx.engine.api.get_logger('插件名')` 获取日志器
5. **声明依赖** — 如果插件依赖其他插件的功能，在 `dependencies` 中声明
6. **游戏逻辑放程序，引擎扩展放插件** — 不要在插件中实现游戏状态
