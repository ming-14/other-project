"""推箱子游戏入口"""

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.game_loop import GameLoop


def setup_logging() -> None:
    log_dir = "logs"
    import os
    os.makedirs(log_dir, exist_ok=True)
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(os.path.join(log_dir, "sokoban.log"), encoding="utf-8"),
        ],
    )


def main() -> None:
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("推箱子游戏启动")

    use_color = True
    if "--no-color" in sys.argv:
        use_color = False

    game = GameLoop(use_color=use_color)
    game.run()


if __name__ == "__main__":
    main()
