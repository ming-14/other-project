"""模型级参数覆盖模型

定义单个模型的参数覆盖配置与元数据。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from core.models.base import LimitRule


@dataclass
class ModelOverride:
    """单个模型的参数覆盖（None 表示继承 API Key 级别）与元数据"""
    model_id: str
    enabled: bool = True
    groups: list[str] = field(default_factory=lambda: ["other"])
    context_length: Optional[int] = None
    output_length: Optional[int] = None
    max_concurrency: Optional[int] = None
    timeout: Optional[int] = None
    max_errors: Optional[int] = None
    max_requests: Optional[int] = None
    failure_pause: Optional[int] = None
    rate_limits: list[LimitRule] = field(default_factory=list)
    # ── 元数据（来自 api.json） ──
    name: str = ""
    family: str = ""
    reasoning: Optional[bool] = None
    tool_call: Optional[bool] = None
    attachment: Optional[bool] = None
    modalities: Optional[dict] = None
    knowledge: str = ""

    def to_dict(self) -> dict:
        d = {"model_id": self.model_id}
        if not self.enabled:
            d["enabled"] = False
        if self.groups != ["other"]:
            d["groups"] = self.groups
        if self.context_length is not None:
            d["context-length"] = self.context_length
        if self.output_length is not None:
            d["output-length"] = self.output_length
        errors_dict = self._errors_to_dict()
        if errors_dict is not None:
            d["errors"] = errors_dict
        if self.max_requests is not None:
            d["max_requests"] = self.max_requests
        if self.rate_limits:
            d["rate_limits"] = [r.to_dict() for r in self.rate_limits]
        if self.name:
            d["name"] = self.name
        if self.family:
            d["family"] = self.family
        if self.reasoning:
            d["reasoning"] = self.reasoning
        if self.tool_call:
            d["tool_call"] = self.tool_call
        if self.attachment:
            d["attachment"] = self.attachment
        if self.modalities is not None:
            d["modalities"] = self.modalities
        if self.knowledge:
            d["knowledge"] = self.knowledge
        return d

    def _errors_to_dict(self) -> dict | None:
        from core.models.base import ErrorConfig
        ec = ErrorConfig(
            max_concurrency=self.max_concurrency,
            timeout=self.timeout,
            max_errors=self.max_errors,
            failure_pause=self.failure_pause,
        )
        return ec.to_dict()

    @classmethod
    def from_dict(cls, data: dict) -> ModelOverride:
        errors_data = data.get("errors", {}) or {}
        rate_limits = []
        if data.get("rate_limits"):
            rate_limits = [LimitRule.from_dict(r) for r in data["rate_limits"]]
        return cls(
            model_id=data["model_id"],
            enabled=data.get("enabled", True),
            groups=data.get("groups", ["other"]),
            context_length=data.get("context-length"),
            output_length=data.get("output-length"),
            max_concurrency=errors_data.get("max_concurrency"),
            timeout=errors_data.get("timeout"),
            max_errors=errors_data.get("max_errors"),
            failure_pause=errors_data.get("failure_pause"),
            max_requests=data.get("max_requests"),
            rate_limits=rate_limits,
            # ── 元数据 ──
            name=data.get("name", ""),
            family=data.get("family", ""),
            reasoning=data.get("reasoning"),
            tool_call=data.get("tool_call"),
            attachment=data.get("attachment"),
            modalities=data.get("modalities"),
            knowledge=data.get("knowledge", ""),
        )
