"""!
@file programs/maze/main.py
@brief 迷宫程序入口
"""

from core.engine.game import Engine
from programs.maze.maze_program import MazeProgram


def main():
    engine = Engine()
    engine.set_program(MazeProgram())
    engine.run()


if __name__ == '__main__':
    main()
