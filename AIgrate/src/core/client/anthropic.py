"""Anthropic Messages API 手动处理

因 openai SDK 不兼容 Anthropic 格式，提供手动 SSE 流式解析。
"""

from __future__ import annotations

import json
from typing import Optional, Callable, Generator
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from core.client.factory import (
    ssl_context,
    anthropic_headers,
    anthropic_chat_url,
    anthropic_chat_body,
)


def parse_anthropic_stream(data_str: str):
    """解析 Anthropic 流式响应块

    Args:
        data_str: JSON 数据字符串

    Returns:
        (content, reasoning, usage) 三元组
        content:   文本内容 str，None 表示流结束，"" 表示无内容
        reasoning: 推理内容（Anthropic 无此字段，恒为 ""）
        usage:     dict 或 None
    """
    try:
        obj = json.loads(data_str)
        event_type = obj.get("type", "")
        if event_type == "content_block_delta":
            delta = obj.get("delta", {})
            text = delta.get("text", "")
            return (text, "", None) if text else ("", "", None)
        elif event_type == "message_stop":
            return (None, "", None)
        return ("", "", None)
    except (json.JSONDecodeError, KeyError):
        return ("", "", None)


def stream_chat_anthropic(
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict],
    params: Optional[dict] = None,
    stop_check: Optional[Callable[[], bool]] = None,
    timeout: int = 60,
    on_reasoning: Optional[Callable[[str], None]] = None,
    on_usage: Optional[Callable[[dict], None]] = None,
) -> Generator[str, None, None]:
    """Anthropic Messages API 流式请求（手动 SSE 解析）"""
    url = anthropic_chat_url(base_url)
    body_dict = anthropic_chat_body(model, messages, params, stream=True)
    body = json.dumps(body_dict).encode()
    headers = anthropic_headers(api_key)
    req = Request(url, data=body, headers=headers, method="POST")

    try:
        resp = urlopen(req, context=ssl_context(), timeout=timeout)
    except HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        raise Exception(f"HTTP {e.code} {e.reason}\n{err_body}")
    except Exception as e:
        raise Exception(str(e))

    buffer = ""
    for raw_chunk in resp:
        if stop_check and stop_check():
            resp.close()
            return
        buffer += raw_chunk.decode("utf-8", errors="replace")
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            line = line.strip()
            if not line:
                continue
            if line.startswith("data: "):
                data_str = line[6:]
                content, reasoning, usage = parse_anthropic_stream(data_str)
                if content is None:
                    return
                if reasoning and on_reasoning:
                    on_reasoning(reasoning)
                if usage is not None and on_usage:
                    on_usage(usage)
                if content:
                    yield content