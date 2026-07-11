"""!
@file main.py
@brief 游戏入口

默认运行迷宫程序。可通过命令行参数选择程序:
  python main.py              -> 迷宫
  python main.py temple_run   -> 神庙逃亡
"""

import sys
from core.engine.game import Engine


def main():
    program_name = sys.argv[1] if len(sys.argv) > 1 else 'maze'

    engine = Engine()

    if program_name == 'temple_run':
        from programs.temple_run.temple_run_program import TempleRunProgram
        engine.set_program(TempleRunProgram())
    else:
        from programs.maze.maze_program import MazeProgram
        engine.set_program(MazeProgram())

    engine.run()


if __name__ == '__main__':
    main()
