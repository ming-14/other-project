"""核心实体模型

定义 AI 池（多 key 路由）与普通 AI（单连接）两种核心实体。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from core.models.apikey import ApiKeyConfig
from core.models.overrides import ModelOverride


@dataclass
class AIPool:
    """AI 池（多 key 路由 + 故障转移）"""
    name: str
    enabled: bool = True
    keys: list[ApiKeyConfig] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = {"type": "pool", "name": self.name, "keys": [kc.to_dict() for kc in self.keys]}
        if not self.enabled:
            d["enabled"] = False
        return d

    @classmethod
    def from_dict(cls, data: dict) -> AIPool:
        return cls(
            name=data["name"],
            enabled=data.get("enabled", True),
            keys=[ApiKeyConfig.from_dict(kd) for kd in data.get("keys", [])],
        )


@dataclass
class SingleAI:
    """普通 AI（单连接多模型，不走路由）"""
    name: str
    alias: str = ""
    enabled: bool = True
    key: ApiKeyConfig = field(default_factory=lambda: ApiKeyConfig(base_url="", api_key=""))
    models: dict[str, ModelOverride] = field(default_factory=dict)

    def get_id(self) -> str:
        """返回用于 /model 切换的标识（优先 alias，否则 name）"""
        return self.alias or self.name

    def get_model_ids(self) -> list[str]:
        return list(self.models.keys())

    def to_dict(self) -> dict:
        key_dict = self.key.to_dict()
        key_dict.pop("models", None)
        key_dict.pop("errors", None)
        key_dict.pop("rate_limits", None)
        d = {
            "type": "single",
            "name": self.name,
            "enabled": self.enabled,
            "key": key_dict,
            "models": {mid: mo.to_dict() for mid, mo in self.models.items()},
        }
        if self.alias:
            d["alias"] = self.alias
        return d

    @classmethod
    def from_dict(cls, data: dict) -> SingleAI:
        key_data = data.get("key", {})
        key_data.pop("models", None)
        key = ApiKeyConfig.from_dict(key_data)
        key.models = {}
        raw_models = data.get("models", [])
        # 向后兼容：
        #   list[str]          -> 转为 dict[str, ModelOverride]
        #   list[dict]         -> 提取 model_id 转 dict
        #   dict[str, dict]    -> 直接解析为 ModelOverride
        models: dict[str, ModelOverride] = {}
        if isinstance(raw_models, dict):
            for mid, mo_d in raw_models.items():
                if isinstance(mo_d, dict):
                    mo_d.setdefault("model_id", mid)
                    models[mid] = ModelOverride.from_dict(mo_d)
                else:
                    models[mid] = ModelOverride(model_id=mid)
        elif isinstance(raw_models, list):
            for m in raw_models:
                if isinstance(m, str):
                    models[m] = ModelOverride(model_id=m)
                elif isinstance(m, dict):
                    mid = m.get("model_id", "")
                    if mid:
                        models[mid] = ModelOverride.from_dict(m)
        return cls(
            name=data["name"],
            alias=data.get("alias", ""),
            enabled=data.get("enabled", True),
            key=key,
            models=models,
        )
