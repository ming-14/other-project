"""LayoutEngine像素引擎集成测试"""

import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from engine.render.layout_engine import LayoutEngine
from engine.data.levels import get_level, level_count
from engine.logic.map_engine import MapEngine


class TestLayoutEnginePixelRender:
    def test_render_level0(self):
        le = LayoutEngine(use_color=True)
        le.init(24, 80)
        game_map = MapEngine.parse(get_level(0))
        le.render(game_map, 0, level_count(), 0, 0, "playing")
        assert le.buffer is not None

    def test_render_all_levels(self):
        le = LayoutEngine(use_color=True)
        le.init(30, 80)
        for i in range(level_count()):
            game_map = MapEngine.parse(get_level(i))
            le.render(game_map, i, level_count(), 0, 0, "playing")

    def test_render_no_color(self):
        le = LayoutEngine(use_color=False)
        le.init(24, 80)
        game_map = MapEngine.parse(get_level(0))
        le.render(game_map, 0, level_count(), 0, 0, "playing")

    def test_render_won_state(self):
        le = LayoutEngine(use_color=True)
        le.init(24, 80)
        game_map = MapEngine.parse(get_level(0))
        le.render(game_map, 0, level_count(), 1, 1, "won")

    def test_render_all_clear_state(self):
        le = LayoutEngine(use_color=True)
        le.init(24, 80)
        game_map = MapEngine.parse(get_level(0))
        le.render(game_map, 0, level_count(), 5, 3, "all_clear")

    def test_buffer_has_content(self):
        le = LayoutEngine(use_color=True)
        le.init(24, 80)
        game_map = MapEngine.parse(get_level(0))
        le.render(game_map, 0, level_count(), 0, 0, "playing")
        has_content = False
        for r in range(le.buffer.rows):
            row = le.buffer.get_row(r)
            if row:
                has_content = True
                break
        assert has_content

    def test_small_terminal(self):
        le = LayoutEngine(use_color=True)
        le.init(20, 60)
        game_map = MapEngine.parse(get_level(0))
        le.render(game_map, 0, level_count(), 0, 0, "playing")
