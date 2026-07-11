"""!
@file world/generators/recursive_backtrack.py
@brief 递归回溯迷宫生成器

使用深度优先递归回溯算法生成完美迷宫。
"""

import random
from typing import Optional

from world.generators.base import MazeGenerator


class RecursiveBacktrackGenerator(MazeGenerator):
    """!@brief 递归回溯迷宫生成器"""

    @property
    def name(self) -> str:
        return 'recursive_backtrack'

    @property
    def description(self) -> str:
        return '递归回溯(DFS)算法，生成无环完美迷宫'

    def generate(self, width: int, height: int,
                 seed: Optional[int] = None) -> list[list[int]]:
        width, height = self.validate_size(width, height)
        rng = random.Random(seed)
        grid = [[1 for _ in range(width)] for _ in range(height)]

        sx, sy = 1, 1
        grid[sy][sx] = 0
        stack = [(sx, sy)]
        directions = [(2, 0), (-2, 0), (0, 2), (0, -2)]

        while stack:
            cx, cy = stack[-1]
            neighbors = []
            for dx, dy in directions:
                nx, ny = cx + dx, cy + dy
                if 0 < nx < width - 1 and 0 < ny < height - 1:
                    if grid[ny][nx] == 1:
                        neighbors.append((nx, ny, dx, dy))
            if neighbors:
                nx, ny, dx, dy = rng.choice(neighbors)
                grid[cy + dy // 2][cx + dx // 2] = 0
                grid[ny][nx] = 0
                stack.append((nx, ny))
            else:
                stack.pop()

        ex, ey = width - 2, height - 2
        grid[ey][ex] = 2

        return grid
