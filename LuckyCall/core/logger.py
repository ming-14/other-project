import logging
import os
from datetime import datetime


def setup_logger() -> logging.Logger:
    """初始化日志系统，同时输出到控制台和文件"""
    logger = logging.getLogger("luckycall")
    logger.setLevel(logging.DEBUG)

    if logger.handlers:
        return logger

    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
    os.makedirs(log_dir, exist_ok=True)

    now = datetime.now()
    timestamp = now.strftime("%Y%m%d-%H%M%S") + f"-{now.microsecond // 1000:03d}"
    log_file = os.path.join(log_dir, f"luckycall-{timestamp}.log")

    formatter = logging.Formatter(
        fmt="%(asctime)s.%(msecs)03d | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logger.info("日志系统初始化完成，日志文件: %s", log_file)
    return logger


def get_logger(name: str) -> logging.Logger:
    """获取子模块日志器"""
    return logging.getLogger(f"luckycall.{name}")
