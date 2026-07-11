"""!
@file world/generators/__init__.py
@brief 迷宫生成器包
"""

from world.generators.base import MazeGenerator
from world.generators.recursive_backtrack import RecursiveBacktrackGenerator

__all__ = ['MazeGenerator', 'RecursiveBacktrackGenerator']
