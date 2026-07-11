"""!
@file render/ui/base.py
@brief UI组件抽象基类

定义可叠加到渲染画面的UI组件接口。
"""

from abc import ABC, abstractmethod
from typing import Any


class UIComponent(ABC):
    """!@brief UI组件协议

    所有UI组件必须实现此接口。
    UI组件在场景渲染后、输出前绘制。
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """!@brief 组件名称"""
        ...

    @property
    def visible(self) -> bool:
        """!@brief 是否可见"""
        return self._visible

    def __init__(self):
        self._visible = True

    def show(self) -> None:
        """!@brief 显示"""
        self._visible = True

    def hide(self) -> None:
        """!@brief 隐藏"""
        self._visible = False

    def toggle(self) -> None:
        """!@brief 切换可见性"""
        self._visible = not self._visible

    @abstractmethod
    def draw(self, buffer: Any, context: dict) -> None:
        """!@brief 绘制UI

        @param buffer  像素缓冲区
        @param context 渲染上下文
        """
        ...


class TextOverlay(UIComponent):
    """!@brief 文本叠加层

    在指定位置绘制文本到像素缓冲区。
    """

    @property
    def name(self) -> str:
        return 'text_overlay'

    def __init__(self, text: str = '', x: int = 1, y: int = 1,
                 color: tuple = (240, 240, 240)):
        super().__init__()
        self.text = text
        self.x = x
        self.y = y
        self.color = color

    def draw(self, buffer: Any, context: dict) -> None:
        if not self._visible or not self.text:
            return
        pass


class ProgressBar(UIComponent):
    """!@brief 进度条UI组件"""

    @property
    def name(self) -> str:
        return 'progress_bar'

    def __init__(self, x: int = 1, y: int = 1, width: int = 20,
                 fill_color: tuple = (60, 200, 90),
                 empty_color: tuple = (40, 40, 40)):
        super().__init__()
        self.x = x
        self.y = y
        self.width = width
        self.fill_color = fill_color
        self.empty_color = empty_color
        self.ratio = 1.0

    def draw(self, buffer: Any, context: dict) -> None:
        if not self._visible:
            return
        fill_w = max(0, min(self.width, int(self.width * self.ratio)))
        fill_pack = (self.fill_color[0] << 16) | (self.fill_color[1] << 8) | self.fill_color[2]
        empty_pack = (self.empty_color[0] << 16) | (self.empty_color[1] << 8) | self.empty_color[2]
        if self.y < buffer.pixel_height:
            row = buffer.data[self.y]
            for i in range(self.width):
                px = self.x + i
                if px < buffer.width:
                    row[px] = fill_pack if i < fill_w else empty_pack
