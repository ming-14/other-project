"""!
@file plugins/minimap_plugin.py
@brief 小地图插件

在像素缓冲区左上角绘制迷宫小地图，标注玩家位置与出口。
作为渲染层注册到 RenderPipeline，可通过插件系统卸载/禁用。
"""

from core.engine.plugin import Plugin, PluginContext
from core.event_bus import EventType
from config import (MINIMAP_WALL, MINIMAP_PATH, MINIMAP_PLAYER,
                    MINIMAP_EXIT, MINIMAP_SCALE)

_MM_WALL = (MINIMAP_WALL[0] << 16) | (MINIMAP_WALL[1] << 8) | MINIMAP_WALL[2]
_MM_PATH = (MINIMAP_PATH[0] << 16) | (MINIMAP_PATH[1] << 8) | MINIMAP_PATH[2]
_MM_PLAYER = (MINIMAP_PLAYER[0] << 16) | (MINIMAP_PLAYER[1] << 8) | MINIMAP_PLAYER[2]
_MM_EXIT = (MINIMAP_EXIT[0] << 16) | (MINIMAP_EXIT[1] << 8) | MINIMAP_EXIT[2]

_CELL_COLORS = {0: _MM_PATH, 1: _MM_WALL, 2: _MM_EXIT}


class MinimapLayer:
    """!@brief 小地图渲染层

    实现 on_render(context) 接口，作为渲染层注册到 RenderPipeline。
    """

    def __init__(self, maze=None):
        self._maze = maze
        self._visible = True

    def set_maze(self, maze):
        self._maze = maze

    @property
    def visible(self) -> bool:
        return self._visible

    def show(self):
        self._visible = True

    def hide(self):
        self._visible = False

    def toggle(self):
        self._visible = not self._visible

    def on_render(self, context: dict) -> None:
        if not self._visible:
            return
        maze = self._maze or context.get('maze')
        player = context.get('player')
        buffer = context.get('buffer')
        if maze is None or player is None or buffer is None:
            return
        self.draw(buffer, player, maze)

    def draw(self, buffer, player, maze=None):
        maze = maze or self._maze
        if maze is None:
            return
        mw = maze.width
        mh = maze.height
        scale = MINIMAP_SCALE
        ox = 1
        oy = 1
        data = buffer.data
        bw = buffer.width
        bph = buffer.pixel_height
        cell_colors = _CELL_COLORS
        grid = maze.grid

        for my in range(mh):
            for mx in range(mw):
                color = cell_colors[grid[my][mx]]
                for dy in range(scale):
                    py = oy + my * scale + dy
                    if py >= bph:
                        break
                    row = data[py]
                    for dx in range(scale):
                        px = ox + mx * scale + dx
                        if px < bw:
                            row[px] = color

        ppx = ox + player.x * scale
        ppy = oy + player.y * scale
        buffer.set_pixel(ppx, ppy, _MM_PLAYER)


class MinimapPlugin(Plugin):
    """!@brief 小地图插件

    将小地图渲染层注册到渲染管线，并监听迷宫重新生成事件更新引用。
    """

    @property
    def name(self) -> str:
        return 'minimap'

    @property
    def description(self) -> str:
        return '左上角迷宫小地图，显示玩家位置与出口'

    def on_load(self, ctx: PluginContext) -> None:
        self._ctx = ctx
        self._layer = MinimapLayer(ctx.engine.maze)
        ctx.renderer.add_layer('minimap', self._layer, priority=10)
        ctx.events.subscribe(EventType.WORLD_MAZE_GENERATED, self._on_maze_generated)
        ctx.engine.api.bind_action('minimap_toggle', self._on_toggle)

    def on_unload(self, ctx: PluginContext) -> None:
        ctx.renderer.remove_layer('minimap')
        ctx.events.unsubscribe(EventType.WORLD_MAZE_GENERATED, self._on_maze_generated)
        ctx.engine.api.unbind_action('minimap_toggle')

    def on_enable(self) -> None:
        self._layer.show()

    def on_disable(self) -> None:
        self._layer.hide()

    def _on_maze_generated(self, data) -> None:
        if self._ctx:
            self._layer.set_maze(self._ctx.engine.maze)

    def _on_toggle(self, pressed: bool) -> None:
        if pressed:
            self._layer.toggle()
