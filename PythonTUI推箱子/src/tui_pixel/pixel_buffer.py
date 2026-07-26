"""PixelBuffer - 像素缓冲区，2D像素数组，支持贴图blit与alpha混合"""

from __future__ import annotations

from .color import Color, TRANSPARENT

PixelRow = tuple[Color, ...]
PixelData = tuple[PixelRow, ...]


class PixelBuffer:
    """2D像素缓冲区，每个像素为Color(含alpha通道)

    坐标系: (x, y)，x向右为正(列)，y向下为正(行)
    内部存储: _data[y][x]，行优先
    """

    def __init__(self, width: int, height: int) -> None:
        if width <= 0 or height <= 0:
            raise ValueError(f"宽高必须为正整数: {width}x{height}")
        self._width = width
        self._height = height
        self._data: list[list[Color]] = [
            [TRANSPARENT] * width for _ in range(height)
        ]

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    def get_pixel(self, x: int, y: int) -> Color:
        """获取指定位置像素，越界返回TRANSPARENT"""
        if 0 <= x < self._width and 0 <= y < self._height:
            return self._data[y][x]
        return TRANSPARENT

    def set_pixel(self, x: int, y: int, color: Color) -> None:
        """设置指定位置像素，越界忽略"""
        if 0 <= x < self._width and 0 <= y < self._height:
            self._data[y][x] = color

    def fill(self, color: Color) -> None:
        """整体填充"""
        for y in range(self._height):
            for x in range(self._width):
                self._data[y][x] = color

    def clear(self) -> None:
        """清空为全透明"""
        self.fill(TRANSPARENT)

    def blit(self, sprite_data: PixelData, x: int, y: int) -> None:
        """将贴图数据blit到缓冲区指定位置，支持alpha混合

        Args:
            sprite_data: 贴图像素数据，tuple of rows，每行tuple of Color
            x: 目标左上角x坐标
            y: 目标左上角y坐标
        alpha=0的像素不覆盖目标(全透明跳过)
        alpha=255的像素直接覆盖(全不透明)
        0<alpha<255的像素做alpha混合
        """
        for sy, row in enumerate(sprite_data):
            dy = y + sy
            if dy < 0 or dy >= self._height:
                continue
            for sx, pixel in enumerate(row):
                if pixel.is_transparent:
                    continue
                dx = x + sx
                if 0 <= dx < self._width:
                    if pixel.is_opaque:
                        self._data[dy][dx] = pixel
                    else:
                        self._data[dy][dx] = pixel.alpha_blend(self._data[dy][dx])

    def blit_buffer(self, src: PixelBuffer, x: int, y: int) -> None:
        """将另一个PixelBuffer blit到本缓冲区，支持alpha混合"""
        for sy in range(src._height):
            dy = y + sy
            if dy < 0 or dy >= self._height:
                continue
            for sx in range(src._width):
                pixel = src._data[sy][sx]
                if pixel.is_transparent:
                    continue
                dx = x + sx
                if 0 <= dx < self._width:
                    if pixel.is_opaque:
                        self._data[dy][dx] = pixel
                    else:
                        self._data[dy][dx] = pixel.alpha_blend(self._data[dy][dx])

    def crop(self, x: int, y: int, w: int, h: int) -> PixelBuffer:
        """裁剪子区域，返回新的PixelBuffer"""
        result = PixelBuffer(w, h)
        for sy in range(h):
            for sx in range(w):
                pixel = self.get_pixel(x + sx, y + sy)
                if not pixel.is_transparent:
                    result._data[sy][sx] = pixel
        return result

    def to_data(self) -> PixelData:
        """导出为不可变的tuple数据"""
        return tuple(
            tuple(row) for row in self._data
        )

    @classmethod
    def from_data(cls, data: PixelData) -> PixelBuffer:
        """从tuple数据创建PixelBuffer"""
        height = len(data)
        if height == 0:
            raise ValueError("数据不能为空")
        width = len(data[0])
        if width == 0:
            raise ValueError("行宽不能为0")
        buf = cls(width, height)
        for y, row in enumerate(data):
            if len(row) != width:
                raise ValueError(f"第{y}行宽度不一致: 期望{width}，实际{len(row)}")
            for x, pixel in enumerate(row):
                buf._data[y][x] = pixel
        return buf

    def __repr__(self) -> str:
        return f"PixelBuffer({self._width}x{self._height})"

    def debug_dump(self) -> str:
        """Debug接口: 返回ASCII艺术预览

        不透明→█，半透明≈，透明→·
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

    def debug_pixel_at(self, x: int, y: int) -> str:
        """Debug接口: 返回指定像素的描述"""
        pixel = self.get_pixel(x, y)
        if pixel.is_transparent:
            return f"({x},{y}): transparent"
        return f"({x},{y}): {pixel}"

    def debug_row(self, y: int) -> str:
        """Debug接口: 返回指定行的颜色列表"""
        if not (0 <= y < self._height):
            return f"row {y}: out of range"
        parts: list[str] = []
        for x in range(self._width):
            parts.append(repr(self._data[y][x]))
        return f"row {y}: [{', '.join(parts)}]"
