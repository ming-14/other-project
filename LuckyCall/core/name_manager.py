import random
from enum import Enum, auto
from core.logger import get_logger

logger = get_logger("name_manager")


class CallMode(Enum):
    RANDOM = "random"
    DEDUP = "dedup"


class CallState(Enum):
    IDLE = auto()
    ROLLING = auto()
    STOPPED = auto()


class NameManager:
    """名单管理与抽取逻辑"""

    def __init__(self, names: list, mode: CallMode = CallMode.RANDOM, pick_count: int = 1):
        self._all_names: list = list(names)
        self._mode: CallMode = mode
        self._pick_count: int = pick_count
        self._remaining: list = list(names)
        self._picked: list = []
        self._state: CallState = CallState.IDLE
        self._current_display: str = ""
        logger.info("NameManager 初始化，模式: %s，名单人数: %d", mode.value, len(names))

    @property
    def mode(self) -> CallMode:
        return self._mode

    @mode.setter
    def mode(self, value: CallMode) -> None:
        self._mode = value
        logger.info("切换点名模式: %s", value.value)

    @property
    def pick_count(self) -> int:
        return self._pick_count

    @pick_count.setter
    def pick_count(self, value: int) -> None:
        self._pick_count = max(1, value)

    @property
    def state(self) -> CallState:
        return self._state

    @property
    def current_display(self) -> str:
        return self._current_display

    @property
    def picked(self) -> list:
        return list(self._picked)

    @property
    def remaining_count(self) -> int:
        return len(self._remaining)

    @property
    def all_names(self) -> list:
        return list(self._all_names)

    def update_names(self, names: list) -> None:
        """更新完整名单"""
        self._all_names = list(names)
        self._remaining = list(names)
        self._picked = []
        self._state = CallState.IDLE
        logger.info("名单已更新，共 %d 人", len(names))

    def start(self) -> None:
        """开始点名，进入滚动状态"""
        if self._mode == CallMode.DEDUP and len(self._remaining) == 0:
            logger.warning("候选池已空，无法开始点名")
            return
        self._state = CallState.ROLLING
        self._picked = []
        logger.info("开始点名，模式: %s，抽取人数: %d", self._mode.value, self._pick_count)

    def roll(self) -> str:
        """获取一个随机名字用于闪动显示"""
        if self._mode == CallMode.DEDUP:
            pool = self._remaining
        else:
            pool = self._all_names

        if not pool:
            self._current_display = ""
            return ""

        self._current_display = random.choice(pool)
        return self._current_display

    def stop(self) -> list:
        """停止点名，确定抽取结果"""
        if self._state != CallState.ROLLING:
            return []

        count = min(self._pick_count, len(self._remaining) if self._mode == CallMode.DEDUP else len(self._all_names))
        if count == 0:
            self._state = CallState.STOPPED
            return []

        if self._mode == CallMode.DEDUP:
            results = random.sample(self._remaining, count)
            for name in results:
                self._remaining.remove(name)
        else:
            results = random.choices(self._all_names, k=count)

        self._picked = results
        self._current_display = "、".join(results)
        self._state = CallState.STOPPED
        logger.info("点名结果: %s (模式: %s)", "、".join(results), self._mode.value)
        return results

    def reset(self) -> None:
        """重置候选池（去重模式用）"""
        self._remaining = list(self._all_names)
        self._picked = []
        self._state = CallState.IDLE
        self._current_display = ""
        logger.info("候选池已重置，共 %d 人", len(self._remaining))

    def is_exhausted(self) -> bool:
        """去重模式下是否已全部抽完"""
        if self._mode == CallMode.RANDOM:
            return False
        return len(self._remaining) == 0

    def is_insufficient(self) -> bool:
        """去重模式下剩余人数是否不足"""
        if self._mode == CallMode.RANDOM:
            return False
        return len(self._remaining) < self._pick_count
