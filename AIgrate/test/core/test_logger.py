import pytest
from core.log.logger import get_logger


class TestGetLogger:
    def test_returns_logger(self):
        logger = get_logger("TestModule")
        assert logger is not None
        assert logger.name == "aipool.TestModule"

    def test_returns_child_of_aipool(self):
        logger = get_logger("Another")
        assert logger.parent is not None
        assert logger.parent.name == "aipool"

    def test_different_names_return_different_loggers(self):
        l1 = get_logger("Mod1")
        l2 = get_logger("Mod2")
        assert l1 is not l2
        assert l1.name != l2.name

    def test_same_name_returns_same_logger(self):
        l1 = get_logger("Same")
        l2 = get_logger("Same")
        assert l1 is l2