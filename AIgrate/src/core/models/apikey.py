"""API Key 配置模型

定义单个 API Key 的完整配置数据结构。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from core.models.base import VALID_API_TYPES, LimitRule, ErrorConfig
from core.models.overrides import ModelOverride


@dataclass
class ApiKeyConfig:
    """一个 API Key 的完整配置"""
    base_url: str
    api_key: str
    type: str = "openai"
    label: str = ""
    enabled: bool = True
    groups: list[str] = field(default_factory=lambda: ["other"])
    max_requests: Optional[int] = None
    errors: ErrorConfig = field(default_factory=lambda: ErrorConfig(
        max_concurrency=1, timeout=30, max_errors=3, failure_pause=40
    ))
    rate_limits: Optional[list[LimitRule]] = None
    models: dict[str, ModelOverride] = field(default_factory=dict)

    def __post_init__(self):
        if self.type not in VALID_API_TYPES:
            from core.log.logger import get_logger
            get_logger("models").warning("未知 API 类型: %s，有效值: %s", self.type, VALID_API_TYPES)

    def get_model_ids(self) -> list[str]:
        return list(self.models.keys())

    def to_dict(self) -> dict:
        d = {
            "type": self.type,
            "base_url": self.base_url,
            "api_key": self.api_key,
            "label": self.label,
            "enabled": self.enabled,
            "models": {mid: mo.to_dict() for mid, mo in self.models.items()},
        }
        errors_dict = self.errors.to_dict()
        if errors_dict is not None:
            d["errors"] = errors_dict
        if self.groups != ["other"]:
            d["groups"] = self.groups
        if self.max_requests is not None:
            d["max_requests"] = self.max_requests
        if self.rate_limits:
            d["rate_limits"] = [r.to_dict() for r in self.rate_limits]
        return d

    @classmethod
    def from_dict(cls, data: dict) -> ApiKeyConfig:
        rate_limits = None
        if data.get("rate_limits"):
            rate_limits = [LimitRule.from_dict(r) for r in data["rate_limits"]]
        models = {}
        for mid, mo_d in data.get("models", {}).items():
            models[mid] = ModelOverride.from_dict(mo_d)
        return cls(
            type=data.get("type", "openai"),
            base_url=data["base_url"],
            api_key=data["api_key"],
            label=data.get("label", ""),
            enabled=data.get("enabled", True),
            groups=data.get("groups", ["other"]),
            errors=ErrorConfig.from_dict(data.get("errors")),
            max_requests=data.get("max_requests"),
            rate_limits=rate_limits,
            models=models,
        )