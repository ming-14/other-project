"""客户端工厂与内部辅助

提供根据 API 类型创建 OpenAI/AzureOpenAI 客户端的工厂函数，
以及 Anthropic 请求构建和 SSL 上下文等内部辅助函数。
"""

from __future__ import annotations

import ssl
from typing import Optional

from openai import OpenAI, AzureOpenAI


def create_client(base_url: str, api_key: str, api_type: str = "openai") -> OpenAI | AzureOpenAI:
    """根据 API 类型创建对应的 openai 客户端

    Args:
        base_url: API 基础地址
        api_key:  API Key
        api_type: API 格式类型

    Returns:
        OpenAI 或 AzureOpenAI 客户端实例
    """
    base = base_url.rstrip("/")
    if api_type == "azure":
        return AzureOpenAI(
            api_key=api_key,
            azure_endpoint=base,
            api_version="2024-06-01",
        )
    return OpenAI(api_key=api_key, base_url=base)


def ssl_context() -> ssl.SSLContext:
    """创建不验证证书的 SSL 上下文"""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


# ── Anthropic 请求辅助 ──────────────────────────────────────────────────────


def anthropic_headers(api_key: str) -> dict[str, str]:
    """构建 Anthropic 请求头"""
    return {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }


def anthropic_models_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/models"


def anthropic_chat_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/messages"


def anthropic_chat_body(
    model: str,
    messages: list[dict],
    params: Optional[dict] = None,
    stream: bool = True,
) -> dict:
    """构建 Anthropic 格式的请求体

    从 messages 中提取 system 消息作为顶级 system 字段。
    """
    system_text = ""
    chat_msgs = []
    for m in messages:
        if m.get("role") == "system":
            system_text += m.get("content", "")
        else:
            chat_msgs.append({"role": m["role"], "content": m.get("content", "")})

    body: dict = {
        "model": model,
        "messages": chat_msgs,
        "stream": stream,
        "max_tokens": 4096,
    }
    if system_text:
        body["system"] = system_text
    if params:
        if params.get("max_tokens") is not None:
            body["max_tokens"] = params["max_tokens"]
        if params.get("temperature") is not None:
            body["temperature"] = params["temperature"]
        if params.get("top_p") is not None:
            body["top_p"] = params["top_p"]
    return body