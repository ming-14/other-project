"""基础配置模型

定义 API 类型常量、速率限制规则与错误/并发配置。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# 支持的 API 格式类型
VALID_API_TYPES = {"openai", "azure", "anthropic", "huggingface"}


@dataclass
class LimitRule:
    """速率限制规则"""
    type: str
    time: int
    count: Optional[int] = None
    tokens: Optional[int] = None

    def describe(self) -> str:
        if self.type == "time_per_req":
            return f"{self.time}s/次"
        elif self.type == "count_per_time":
            return f"{self.count}次/{self.time}s"
        elif self.type == "tokens_per_time":
            return f"{self.tokens}token/{self.time}s"
        return str(self)

    def to_dict(self) -> dict:
        d = {"type": self.type, "time": self.time}
        if self.count is not None:
            d["count"] = self.count
        if self.tokens is not None:
            d["tokens"] = self.tokens
        return d

    @classmethod
    def from_dict(cls, data: dict) -> LimitRule:
        return cls(
            type=data["type"],
            time=data["time"],
            count=data.get("count"),
            tokens=data.get("tokens"),
        )


@dataclass
class ErrorConfig:
    """错误/并发/超时相关配置"""
    max_concurrency: Optional[int] = None
    timeout: Optional[int] = None
    max_errors: Optional[int] = None
    failure_pause: Optional[int] = None
    max_errors_model: Optional[int] = None       # apikey 级别：上限后仅禁用该模型
    failure_pause_model: Optional[int] = None    # apikey 级别：冷却仅作用于该模型

    def to_dict(self) -> dict | None:
        d = {}
        if self.max_concurrency is not None:
            d["max_concurrency"] = self.max_concurrency
        if self.timeout is not None:
            d["timeout"] = self.timeout
        if self.max_errors is not None:
            d["max_errors"] = self.max_errors
        if self.failure_pause is not None:
            d["failure_pause"] = self.failure_pause
        if self.max_errors_model is not None:
            d["max_errors_model"] = self.max_errors_model
        if self.failure_pause_model is not None:
            d["failure_pause_model"] = self.failure_pause_model
        return d if d else None

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> ErrorConfig:
        if not data:
            return cls()
        return cls(
            max_concurrency=data.get("max_concurrency"),
            timeout=data.get("timeout"),
            max_errors=data.get("max_errors"),
            failure_pause=data.get("failure_pause"),
            max_errors_model=data.get("max_errors_model"),
            failure_pause_model=data.get("failure_pause_model"),
        )