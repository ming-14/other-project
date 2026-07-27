"""滑动窗口速率限制器

支持三种限制模式：
  - time_per_req:    每窗口内 1 次请求
  - count_per_time:  每窗口内 N 次请求
  - tokens_per_time: 每窗口内 N 个 token
"""

from __future__ import annotations

import threading
import time

from core.models.base import LimitRule


class RateLimiter:
    """滑动窗口速率限制器，线程安全"""

    def __init__(self):
        self._lock = threading.Lock()
        self._records: dict[str, list[tuple[float, int]]] = {}

    def _prune(self, scope: str, max_window: int):
        """清理超出最大窗口的历史事件"""
        now = time.time()
        records = self._records.get(scope, [])
        cutoff = now - max_window
        self._records[scope] = [(t, tk) for t, tk in records if t > cutoff]

    def check(self, scope: str, rules: list[LimitRule]) -> tuple[bool, float]:
        """检查 scope 在当前 rules 下是否允许请求

        Args:
            scope: 限流作用域（如 "rate:key:0"）
            rules: 限流规则列表

        Returns:
            (can_proceed, wait_seconds)
            can_proceed=False 时 wait_seconds 为建议等待秒数
        """
        if not rules:
            return True, 0.0

        with self._lock:
            if scope not in self._records:
                self._records[scope] = []
            max_window = max((r.time for r in rules), default=300)
            self._prune(scope, max_window)

            events = self._records[scope]
            now = time.time()
            max_wait = 0.0

            for rule in rules:
                if rule.type == "time_per_req":
                    if events:
                        last_ts = events[-1][0]
                        elapsed = now - last_ts
                        if elapsed < rule.time:
                            max_wait = max(max_wait, rule.time - elapsed)

                elif rule.type == "count_per_time":
                    if rule.count is None:
                        continue
                    cutoff = now - rule.time
                    count = sum(1 for t, _ in events if t > cutoff)
                    if count >= rule.count:
                        earliest = min(
                            (t for t, _ in events if t > cutoff),
                            default=None,
                        )
                        if earliest is not None:
                            max_wait = max(max_wait, rule.time - (now - earliest))

                elif rule.type == "tokens_per_time":
                    if rule.tokens is None:
                        continue
                    cutoff = now - rule.time
                    total = sum(tk for t, tk in events if t > cutoff)
                    if total >= rule.tokens:
                        earliest = min(
                            (t for t, _ in events if t > cutoff and _ > 0),
                            default=None,
                        )
                        if earliest is not None:
                            max_wait = max(max_wait, rule.time - (now - earliest))

            return max_wait == 0, max_wait

    def record(self, scope: str, tokens: int = 0):
        """记录一次请求

        Args:
            scope:  限流作用域
            tokens: 本次消耗的 token 数
        """
        with self._lock:
            if scope not in self._records:
                self._records[scope] = []
            self._records[scope].append((time.time(), tokens))