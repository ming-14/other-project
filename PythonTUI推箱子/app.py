"""推箱子游戏快捷入口"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from src.main import main

if __name__ == "__main__":
    main()
