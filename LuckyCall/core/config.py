import json
import os
from core.logger import get_logger

logger = get_logger("config")

CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "list.json"
)

DEFAULT_CONFIG = {
    "names": [
        "张三", "李四", "王五", "赵六", "孙七",
        "周八", "吴九", "郑十", "冯十一", "陈十二",
        "褚十三", "卫十四", "蒋十五", "沈十六", "韩十七",
        "杨十八", "朱十九", "秦二十", "尤廿一", "许廿二",
    ],
    "pick_count": 1,
    "animation_interval": 60,
    "theme": "auto",
}


class Config:
    """配置管理器，负责读写 data/list.json"""

    def __init__(self):
        self._data: dict = {}
        self.load()

    def load(self) -> None:
        """从文件加载配置，文件不存在则创建默认配置"""
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
                logger.info("配置加载成功: %s", CONFIG_PATH)
            except (json.JSONDecodeError, IOError) as e:
                logger.error("配置加载失败，使用默认配置: %s", e)
                self._data = dict(DEFAULT_CONFIG)
        else:
            logger.info("配置文件不存在，创建默认配置: %s", CONFIG_PATH)
            self._data = dict(DEFAULT_CONFIG)
            self._ensure_default_keys()
            self.save()

    def _ensure_default_keys(self) -> None:
        """确保所有默认键都存在"""
        for key, value in DEFAULT_CONFIG.items():
            if key not in self._data:
                self._data[key] = value if not isinstance(value, list) else list(value)

    def save(self) -> None:
        """将配置写回文件"""
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
            logger.info("配置保存成功")
        except IOError as e:
            logger.error("配置保存失败: %s", e)

    @property
    def names(self) -> list:
        return list(self._data.get("names", DEFAULT_CONFIG["names"]))

    @names.setter
    def names(self, value: list) -> None:
        self._data["names"] = list(value)
        self.save()
        logger.info("名单已更新，共 %d 人", len(value))

    @property
    def pick_count(self) -> int:
        return self._data.get("pick_count", DEFAULT_CONFIG["pick_count"])

    @pick_count.setter
    def pick_count(self, value: int) -> None:
        self._data["pick_count"] = max(1, min(99, value))
        self.save()
        logger.info("抽取人数已更新: %d", self._data["pick_count"])

    @property
    def animation_interval(self) -> int:
        return self._data.get("animation_interval", DEFAULT_CONFIG["animation_interval"])

    @animation_interval.setter
    def animation_interval(self, value: int) -> None:
        self._data["animation_interval"] = max(20, min(300, value))
        self.save()
        logger.info("闪动间隔已更新: %d ms", self._data["animation_interval"])

    @property
    def theme(self) -> str:
        return self._data.get("theme", DEFAULT_CONFIG["theme"])

    @theme.setter
    def theme(self, value: str) -> None:
        if value in ("auto", "light", "dark"):
            self._data["theme"] = value
            self.save()
            logger.info("主题已更新: %s", value)
