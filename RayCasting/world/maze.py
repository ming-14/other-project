"""!
@file world/maze.py
@brief 迷宫数据结构模块

封装迷宫的生成、查询与出口标记功能。
支持通过MazeGenerator接口注入自定义生成算法。
"""

import random
from typing import Optional

from config import MAZE_WIDTH, MAZE_HEIGHT
from core import log_manager

_logger = log_manager.get_logger('world.maze')

_DEFAULT_GENERATOR = None


def _get_default_generator():
    global _DEFAULT_GENERATOR
    if _DEFAULT_GENERATOR is None:
        from world.generators.recursive_backtrack import RecursiveBacktrackGenerator
        _DEFAULT_GENERATOR = RecursiveBacktrackGenerator()
    return _DEFAULT_GENERATOR


class Maze:
    """!@brief 迷宫数据结构

    封装迷宫的生成、查询与出口标记功能。
    支持通过generator参数注入自定义生成算法。
    """

    def __init__(self, width=MAZE_WIDTH, height=MAZE_HEIGHT, seed=None,
                 generator=None):
        """!@brief 构造并生成迷宫

        @param width     迷宫宽度（必须为奇数）
        @param height    迷宫高度（必须为奇数）
        @param seed      随机种子，用于可复现的迷宫
        @param generator 自定义生成器，为None时使用默认递归回溯
        """
        if width % 2 == 0:
            width += 1
        if height % 2 == 0:
            height += 1
        self.width = width
        self.height = height
        self.seed = seed
        self.generator_name = 'default'
        self.start = (1.5, 1.5)
        self.exit = (width - 2, height - 2)

        if generator is not None:
            self.grid = generator.generate(width, height, seed)
            self.generator_name = generator.name
        else:
            self._rng = random.Random(seed)
            self.grid = [[1 for _ in range(width)] for _ in range(height)]
            self._generate()
            self._mark_exit()

        _logger.info('迷宫已生成: %dx%d, 生成器=%s, 起点(%.1f,%.1f), 出口(%d,%d)',
                      width, height, self.generator_name,
                      self.start[0], self.start[1],
                      self.exit[0], self.exit[1])

    def _generate(self):
        """!@brief 递归回溯算法生成迷宫通道"""
        sx, sy = 1, 1
        self.grid[sy][sx] = 0
        stack = [(sx, sy)]
        directions = [(2, 0), (-2, 0), (0, 2), (0, -2)]

        while stack:
            cx, cy = stack[-1]
            neighbors = []
            for dx, dy in directions:
                nx, ny = cx + dx, cy + dy
                if 0 < nx < self.width - 1 and 0 < ny < self.height - 1:
                    if self.grid[ny][nx] == 1:
                        neighbors.append((nx, ny, dx, dy))
            if neighbors:
                nx, ny, dx, dy = self._rng.choice(neighbors)
                self.grid[cy + dy // 2][cx + dx // 2] = 0
                self.grid[ny][nx] = 0
                stack.append((nx, ny))
            else:
                stack.pop()

    def _mark_exit(self):
        """!@brief 标记迷宫出口位置为特殊值2"""
        ex, ey = self.width - 2, self.height - 2
        self.grid[ey][ex] = 0
        self.exit = (ex, ey)
        self.grid[ey][ex] = 2

    def is_wall(self, x, y):
        """!@brief 判断指定坐标是否为墙壁"""
        ix, iy = int(x), int(y)
        if ix < 0 or iy < 0 or ix >= self.width or iy >= self.height:
            return True
        return self.grid[iy][ix] >= 1

    def cell_type(self, x, y):
        """!@brief 获取单元格类型

        @return 0=通道，1=墙，2=出口
        """
        ix, iy = int(x), int(y)
        if ix < 0 or iy < 0 or ix >= self.width or iy >= self.height:
            return 1
        return self.grid[iy][ix]

    def is_exit(self, x, y):
        """!@brief 判断玩家是否到达出口"""
        return self.cell_type(x, y) == 2

    def set_cell(self, x, y, value):
        """!@brief 设置单元格值（用于动态修改迷宫）

        @param x     列坐标
        @param y     行坐标
        @param value 单元格值（0=通道，1=墙，2=出口）
        """
        ix, iy = int(x), int(y)
        if 0 <= ix < self.width and 0 <= iy < self.height:
            self.grid[iy][ix] = value
