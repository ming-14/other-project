"""!
@file render/pipeline.py
@brief 渲染管线编排模块

编排场景构建、渲染层、后处理效果与终端输出，
提供统一的渲染接口。支持可插拔渲染层和后处理效果。
"""

from typing import Any, Callable, Optional
from render.buffer import PixelBuffer
from render.lighting import Lighting
from render.scene_builder import SceneBuilder
from render.postprocess.base import PostProcessEffect
from render.ui.base import UIComponent
from core import log_manager

_logger = log_manager.get_logger('render.pipeline')

_ANSI_CACHE = {}
_ANSI_FMT = b'\033[38;2;%d;%d;%d;48;2;%d;%d;%dm'
_MAX_CACHE = 8192


class RenderLayer:
    """!@brief 渲染层

    封装一个可排序的渲染步骤。
    """

    __slots__ = ('name', 'renderable', 'priority')

    def __init__(self, name: str, renderable: Any, priority: int = 0):
        self.name = name
        self.renderable = renderable
        self.priority = priority


class RenderPipeline:
    """!@brief 渲染管线

    维护像素缓冲区，编排场景构建、渲染层、后处理、UI与终端输出。
    """

    _HALF_BLOCK = b'\xe2\x96\x80'
    _RESET = b'\033[0m'

    def __init__(self, maze, lighting=None):
        self.maze = maze
        self.lighting = lighting or Lighting()
        self.buffer = PixelBuffer()
        self.scene = SceneBuilder(maze, self.lighting)
        self._layers: list[RenderLayer] = []
        self._post_effects: list[PostProcessEffect] = []
        self._ui_components: dict[str, UIComponent] = []
        self._pre_render_callbacks: list[Callable] = []
        self._post_render_callbacks: list[Callable] = []

    def resize(self):
        return self.buffer.resize()

    @property
    def width(self):
        return self.buffer.width

    @property
    def height(self):
        return self.buffer.height

    # ========================================================================
    # 渲染层管理
    # ========================================================================

    def add_layer(self, name: str, renderable: Any, priority: int = 0) -> None:
        """!@brief 添加渲染层

        @param name     层名称
        @param renderable 实现on_render(context)的对象
        @param priority 优先级，越小越先渲染
        """
        self.remove_layer(name)
        layer = RenderLayer(name, renderable, priority)
        self._layers.append(layer)
        self._layers.sort(key=lambda l: l.priority)

    def remove_layer(self, name: str) -> None:
        """!@brief 移除渲染层"""
        self._layers = [l for l in self._layers if l.name != name]

    # ========================================================================
    # 后处理效果管理
    # ========================================================================

    def add_post_effect(self, effect: PostProcessEffect) -> None:
        """!@brief 添加后处理效果"""
        self.remove_post_effect(effect.name)
        self._post_effects.append(effect)
        self._post_effects.sort(key=lambda e: e.priority)

    def remove_post_effect(self, name: str) -> None:
        """!@brief 移除后处理效果"""
        self._post_effects = [e for e in self._post_effects if e.name != name]

    def get_post_effect(self, name: str) -> Optional[PostProcessEffect]:
        """!@brief 获取后处理效果"""
        for e in self._post_effects:
            if e.name == name:
                return e
        return None

    # ========================================================================
    # UI组件管理
    # ========================================================================

    def add_ui_component(self, component: UIComponent) -> None:
        """!@brief 添加UI组件"""
        self.remove_ui_component(component.name)
        self._ui_components.append(component)

    def remove_ui_component(self, name: str) -> None:
        """!@brief 移除UI组件"""
        self._ui_components = [c for c in self._ui_components if c.name != name]

    # ========================================================================
    # 回调
    # ========================================================================

    def on_pre_render(self, callback: Callable) -> None:
        """!@brief 注册渲染前回调"""
        self._pre_render_callbacks.append(callback)

    def on_post_render(self, callback: Callable) -> None:
        """!@brief 注册渲染后回调"""
        self._post_render_callbacks.append(callback)

    # ========================================================================
    # 渲染
    # ========================================================================

    def render_scene(self, hits, player, camera=None):
        """!@brief 完整渲染流程：场景→精灵→渲染层→后处理→UI"""
        context = {'buffer': self.buffer, 'hits': hits, 'player': player,
                   'maze': self.maze, 'lighting': self.lighting,
                   'camera': camera}

        for cb in self._pre_render_callbacks:
            cb(context)

        self.scene.build(self.buffer, hits, player, camera)

        for layer in self._layers:
            try:
                layer.renderable.on_render(context)
            except Exception as e:
                _logger.error('渲染层 "%s" 异常: %s', layer.name, e)

        for effect in self._post_effects:
            if effect.enabled:
                try:
                    effect.apply(self.buffer, context)
                except Exception as e:
                    _logger.error('后处理 "%s" 异常: %s', effect.name, e)

        for comp in self._ui_components:
            if comp.visible:
                try:
                    comp.draw(self.buffer, context)
                except Exception as e:
                    _logger.error('UI组件 "%s" 异常: %s', comp.name, e)

        for cb in self._post_render_callbacks:
            cb(context)

    def render_to_bytes(self, hud_text=''):
        parts = []
        parts_append = parts.append
        parts_append(b'\033[H')
        half = self._HALF_BLOCK
        reset = self._RESET
        w = self.buffer.width
        cache = _ANSI_CACHE
        cache_get = cache.get
        cache_fmt = _ANSI_FMT
        cache_len = len(cache)
        cache_max = _MAX_CACHE
        for y in range(0, self.buffer.pixel_height, 2):
            row_top = self.buffer.data[y]
            row_bot = self.buffer.data[y + 1]
            x = 0
            while x < w:
                top = row_top[x]
                bot = row_bot[x]
                r0 = (top >> 16) & 0xFF
                g0 = (top >> 8) & 0xFF
                b0 = top & 0xFF
                r1 = (bot >> 16) & 0xFF
                g1 = (bot >> 8) & 0xFF
                b1 = bot & 0xFF
                run = 1
                while x + run < w and row_top[x + run] == top and row_bot[x + run] == bot:
                    run += 1
                key = (r0, g0, b0, r1, g1, b1)
                seq = cache_get(key)
                if seq is None:
                    seq = cache_fmt % (r0, g0, b0, r1, g1, b1)
                    if cache_len < cache_max:
                        cache[key] = seq
                        cache_len += 1
                parts_append(seq)
                parts_append(half * run)
                x += run
            parts_append(reset)
        if hud_text:
            parts_append(b'\033[%d;1H\033[0m' % self.buffer.height)
            parts_append(hud_text.encode('utf-8'))
        return b''.join(parts)

    def render_message(self, message):
        out = ['\033[H']
        for y in range(self.buffer.height):
            row = []
            for x in range(self.buffer.width):
                row.append('\033[48;2;15;15;35m ')
            out.append(''.join(row))
        frame = '\033[0m'.join(out) + '\033[0m'

        lines = message.split('\n')
        start_y = (self.buffer.height - len(lines)) // 2
        for i, line in enumerate(lines):
            x = max(1, (self.buffer.width - len(line)) // 2)
            frame += '\033[%d;%dH\033[38;2;240;240;240m%s' % (start_y + i, x, line)
        frame += '\033[0m'
        return frame
