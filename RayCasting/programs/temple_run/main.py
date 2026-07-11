"""!
@file programs/temple_run/main.py
@brief 神庙逃亡程序入口
"""

from core.engine.game import Engine
from programs.temple_run.temple_run_program import TempleRunProgram


def main():
    engine = Engine()
    engine.set_program(TempleRunProgram())
    engine.run()


if __name__ == '__main__':
    main()
