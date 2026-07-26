"""Sprite - 贴图定义，Sprite与SpriteSheet"""

from __future__ import annotations

from .color import Color, TRANSPARENT
from .pixel_buffer import PixelBuffer, PixelData, PixelRow


class Sprite:
    """贴图：不可变的像素数据，可blit到PixelBuffer

    数据格式: tuple of rows，每行 tuple of Color
    Color.a==0表示透明像素，支持alpha通道
    """

    __slots__ = ("_name", "_data", "_width", "_height")

    def __init__(self, name: str, data: PixelData) -> None:
        self._name = name
        self._height = len(data)
        if self._height == 0:
            raise ValueError(f"贴图'{name}'数据不能为空")
        self._width = len(data[0])
        if self._width == 0:
            raise ValueError(f"贴图'{name}'行宽不能为0")
        for i, row in enumerate(data):
            if len(row) != self._width:
                raise ValueError(
                    f"贴图'{name}'第{i}行宽度不一致: 期望{self._width}，实际{len(row)}"
                )
        self._data = data

    @property
    def name(self) -> str:
        return self._name

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    @property
    def data(self) -> PixelData:
        return self._data

    def get_pixel(self, x: int, y: int) -> Color:
        """获取指定位置像素"""
        if 0 <= x < self._width and 0 <= y < self._height:
            return self._data[y][x]
        return TRANSPARENT

    def to_buffer(self) -> PixelBuffer:
        """转换为PixelBuffer"""
        return PixelBuffer.from_data(self._data)

    def __repr__(self) -> str:
        return f"Sprite('{self._name}', {self._width}x{self._height})"

    def debug_dump(self) -> str:
        """Debug接口: ASCII艺术预览

        不透明→█，半透明≈，全透明→·
        """
        lines: list[str] = []
        for y in range(self._height):
            chars: list[str] = []
            for x in range(self._width):
                p = self._data[y][x]
                if p.is_opaque:
                    chars.append("█")
                elif p.is_transparent:
                    chars.append("·")
                else:
                    chars.append("≈")
            lines.append("".join(chars))
        return "\n".join(lines)


class SpriteSheet:
    """贴图表：名字→Sprite的映射"""

    def __init__(self, name: str = "") -> None:
        self._name = name
        self._sprites: dict[str, Sprite] = {}

    @property
    def name(self) -> str:
        return self._name

    def add(self, sprite: Sprite) -> None:
        """添加贴图"""
        self._sprites[sprite.name] = sprite

    def get(self, name: str) -> Sprite | None:
        """按名查找贴图"""
        return self._sprites.get(name)

    def __getitem__(self, name: str) -> Sprite:
        """按名获取贴图，不存在则KeyError"""
        return self._sprites[name]

    def __contains__(self, name: str) -> bool:
        return name in self._sprites

    @property
    def names(self) -> list[str]:
        return list(self._sprites.keys())

    @property
    def count(self) -> int:
        return len(self._sprites)

    def __repr__(self) -> str:
        return f"SpriteSheet('{self._name}', {self.count} sprites)"

    def debug_dump_all(self) -> str:
        """Debug接口: 输出所有贴图预览"""
        parts: list[str] = []
        for name, sprite in self._sprites.items():
            parts.append(f"--- {name} ({sprite.width}x{sprite.height}) ---")
            parts.append(sprite.debug_dump())
        return "\n".join(parts)
