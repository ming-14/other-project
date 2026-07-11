"""!
@file world/chunk_map.py
@brief 分块无限地图

支持无限延伸的走廊式地图，通过分块生成和回收实现。
对外提供与Maze兼容的接口(is_wall/cell_type)。
"""

import random
from abc import ABC, abstractmethod
from typing import Optional

from core import log_manager

_logger = log_manager.get_logger('world.chunk_map')


class ChunkGenerator(ABC):
    """!@brief 块生成器抽象基类"""

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def generate(self, chunk_x: int, chunk_y: int,
                 size: int, rng: random.Random) -> list:
        ...


class CorridorChunkGenerator(ChunkGenerator):
    """!@brief 走廊风格块生成器"""

    @property
    def name(self) -> str:
        return 'corridor'

    def generate(self, chunk_x, chunk_y, size, rng):
        grid = [[1] * size for _ in range(size)]
        mid = size // 2

        for y in range(size):
            for dx in range(-1, 2):
                if 0 <= mid + dx < size:
                    grid[y][mid + dx] = 0

        if rng.random() < 0.6:
            branch_y = rng.randint(3, size - 4)
            direction = rng.choice(['left', 'right', 'both'])
            if direction in ('left', 'both'):
                for x in range(1, mid - 1):
                    grid[branch_y][x] = 0
                    if rng.random() < 0.3 and branch_y - 1 > 0:
                        grid[branch_y - 1][x] = 0
            if direction in ('right', 'both'):
                for x in range(mid + 2, size - 1):
                    grid[branch_y][x] = 0
                    if rng.random() < 0.3 and branch_y - 1 > 0:
                        grid[branch_y - 1][x] = 0

        for x in range(mid - 1, mid + 2):
            if 0 <= x < size:
                grid[0][x] = 0
                grid[size - 1][x] = 0

        if chunk_x == 0 and chunk_y == 0:
            grid[1][mid] = 0
            grid[1][mid - 1] = 0
            grid[1][mid + 1] = 0

        return grid


class ChunkMap:
    """!@brief 分块无限地图

    替代固定大小的Maze，支持无限延伸。
    对外提供与Maze兼容的 is_wall/cell_type 接口。
    """

    def __init__(self, chunk_size: int = 21, seed: int = None,
                 generator: ChunkGenerator = None):
        self.chunk_size = chunk_size
        self.seed = seed or 42
        self._generator = generator or CorridorChunkGenerator()
        self._chunks: dict[tuple[int, int], list] = {}
        self._view_distance = 3
        self._player_chunk = (None, None)
        self._max_chunks = 100
        self.width = 99999
        self.height = 99999
        mid = chunk_size // 2
        self.start = (mid + 0.5, 1.5)
        self.exit = None
        self.generator_name = self._generator.name

    def _get_chunk(self, cx: int, cy: int) -> list:
        if (cx, cy) not in self._chunks:
            rng = random.Random(self.seed * 1000000 + cx * 1000 + cy)
            self._chunks[(cx, cy)] = self._generator.generate(
                cx, cy, self.chunk_size, rng)
            _logger.debug('生成块 (%d, %d), 当前总块数: %d',
                          cx, cy, len(self._chunks))
        return self._chunks[(cx, cy)]

    def update_player_position(self, x: float, y: float) -> None:
        cx = int(x) // self.chunk_size
        cy = int(y) // self.chunk_size
        if (cx, cy) != self._player_chunk:
            self._player_chunk = (cx, cy)
            self._prefetch_nearby(cx, cy)
            self._recycle_far(cx, cy)

    def _prefetch_nearby(self, cx: int, cy: int) -> None:
        for dx in range(-self._view_distance, self._view_distance + 1):
            for dy in range(-self._view_distance, self._view_distance + 1):
                self._get_chunk(cx + dx, cy + dy)

    def _recycle_far(self, cx: int, cy: int) -> None:
        threshold = self._view_distance + 2
        to_remove = []
        for (kx, ky) in self._chunks:
            if abs(kx - cx) > threshold or abs(ky - cy) > threshold:
                to_remove.append((kx, ky))
        for key in to_remove:
            del self._chunks[key]

    def is_wall(self, x, y) -> bool:
        return self.cell_type(x, y) >= 1

    def cell_type(self, x, y) -> int:
        ix, iy = int(x), int(y)
        if ix < 0 or iy < 0:
            return 1
        cx = ix // self.chunk_size
        cy = iy // self.chunk_size
        chunk = self._get_chunk(cx, cy)
        lx = ix % self.chunk_size
        ly = iy % self.chunk_size
        if 0 <= ly < len(chunk) and 0 <= lx < len(chunk[0]):
            return chunk[ly][lx]
        return 1

    def is_exit(self, x, y) -> bool:
        return False

    def set_cell(self, x, y, value) -> None:
        ix, iy = int(x), int(y)
        if ix < 0 or iy < 0:
            return
        cx = ix // self.chunk_size
        cy = iy // self.chunk_size
        chunk = self._get_chunk(cx, cy)
        lx = ix % self.chunk_size
        ly = iy % self.chunk_size
        if 0 <= ly < len(chunk) and 0 <= lx < len(chunk[0]):
            chunk[ly][lx] = value

    @property
    def grid(self):
        return None

    @property
    def chunk_count(self) -> int:
        return len(self._chunks)


class MazeAdapter:
    """!@brief 将 ChunkMap 适配为 Maze 接口

    使 Raycaster、RenderPipeline 等无需修改即可使用 ChunkMap。
    """

    def __init__(self, chunk_map: ChunkMap):
        self._chunk_map = chunk_map

    def __getattr__(self, name):
        return getattr(self._chunk_map, name)

    @property
    def width(self):
        return self._chunk_map.width

    @property
    def height(self):
        return self._chunk_map.height

    @property
    def grid(self):
        return self._chunk_map.grid

    @property
    def start(self):
        return self._chunk_map.start

    @property
    def exit(self):
        return self._chunk_map.exit
