"""!
@file world/generators/base.py
@brief 迷宫生成器抽象基类

定义迷宫生成器的统一接口，所有自定义生成器必须继承此基类。
"""

from abc import ABC, abstractmethod
from typing import Optional


class MazeGenerator(ABC):
    """!@brief 迷宫生成器协议

    所有迷宫生成算法必须实现此接口。
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """!@brief 生成器名称"""
        ...

    @property
    def description(self) -> str:
        """!@brief 生成器描述"""
        return ''

    @abstractmethod
    def generate(self, width: int, height: int,
                 seed: Optional[int] = None) -> list[list[int]]:
        """!@brief 生成迷宫网格

        @param width  迷宫宽度（必须为奇数）
        @param height 迷宫高度（必须为奇数）
        @param seed   随机种子
        @return 二维网格列表，0=通道，1=墙壁，2=出口
        """
        ...

    def validate_size(self, width: int, height: int) -> tuple[int, int]:
        """!@brief 校验并修正迷宫尺寸为奇数

        @return 修正后的(width, height)
        """
        if width % 2 == 0:
            width += 1
        if height % 2 == 0:
            height += 1
        return width, height
