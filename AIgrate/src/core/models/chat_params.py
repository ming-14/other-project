"""对话参数模型

定义对话请求的参数配置。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ChatParams:
    """对话参数"""
    temperature: float = 0.7
    max_tokens: int = 2048
    top_p: float = 1.0
    system_prompt: str = ""

    def to_dict(self) -> dict:
        return {
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
        }