"""聊天 API 公共接口

提供 test_connection、fetch_models、fetch_model_detail、stream_chat 等
对外公开的 API 调用函数。
"""

from __future__ import annotations

import json

from typing import Optional, Callable, Generator
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from openai import APIStatusError, APIConnectionError

from core.client.factory import (
    create_client,
    ssl_context,
    anthropic_headers,
    anthropic_models_url,
    anthropic_chat_url,
    anthropic_chat_body,
)
from core.client.anthropic import stream_chat_anthropic, parse_anthropic_stream


def test_connection(base_url: str, api_key: str, api_type: str = "openai") -> bool:
    """测试 API 连接是否可用

    Args:
        base_url: API 基础地址
        api_key:  API Key
        api_type: API 格式类型

    Returns:
        连接成功返回 True

    Raises:
        Exception: 连接失败时抛出
    """
    if api_type == "anthropic":
        req = Request(
            anthropic_models_url(base_url),
            headers=anthropic_headers(api_key),
            method="GET",
        )
        try:
            urlopen(req, context=ssl_context(), timeout=10)
            return True
        except HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise Exception(f"HTTP {e.code} {e.reason}\n{body}")
        except Exception as e:
            raise Exception(f"连接测试失败: {e}")

    client = create_client(base_url, api_key, api_type)
    try:
        client.models.list()
        return True
    except APIStatusError as e:
        raise Exception(f"HTTP {e.response.status_code} {e.message}")
    except APIConnectionError as e:
        raise Exception(f"连接测试失败: {e}")
    except Exception as e:
        raise Exception(f"连接测试失败: {e}")


def fetch_models(
    base_url: str, api_key: str, api_type: str = "openai",
) -> tuple[list[str], dict[str, dict]]:
    """获取模型列表及详细信息

    Args:
        base_url: API 基础地址
        api_key:  API Key
        api_type: API 格式类型

    Returns:
        (model_ids, details_dict)

    Raises:
        Exception: 请求失败时抛出
    """
    if api_type == "anthropic":
        req = Request(
            anthropic_models_url(base_url),
            headers=anthropic_headers(api_key),
            method="GET",
        )
        try:
            resp = urlopen(req, context=ssl_context(), timeout=10)
            raw = json.loads(resp.read().decode())
        except HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise Exception(f"HTTP {e.code} {e.reason}\n{body}")
        except Exception as e:
            raise Exception(f"获取模型列表失败: {e}")

        items = raw.get("data", [])
        ids = [m["id"] for m in items if "id" in m]
        details = {m["id"]: m for m in items if "id" in m}
        return ids, details

    client = create_client(base_url, api_key, api_type)
    try:
        models = client.models.list()
        ids = [m.id for m in models]
        details = {m.id: m.model_dump() for m in models}
        return ids, details
    except APIStatusError as e:
        raise Exception(f"HTTP {e.response.status_code} {e.message}")
    except Exception as e:
        raise Exception(f"获取模型列表失败: {e}")


def fetch_model_detail(
    base_url: str, api_key: str, model_id: str, api_type: str = "openai",
) -> dict:
    """获取单个模型的详细信息

    Args:
        base_url: API 基础地址
        api_key:  API Key
        model_id: 模型 ID
        api_type: API 格式类型

    Returns:
        模型信息的字典

    Raises:
        Exception: 请求失败时抛出
    """
    if api_type == "anthropic":
        url = f"{anthropic_models_url(base_url)}/{model_id}"
        req = Request(url, headers=anthropic_headers(api_key), method="GET")
        try:
            resp = urlopen(req, context=ssl_context(), timeout=10)
            return json.loads(resp.read().decode())
        except HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise Exception(f"HTTP {e.code} {e.reason}\n{body}")
        except Exception as e:
            raise Exception(f"获取模型详情失败: {e}")

    client = create_client(base_url, api_key, api_type)
    try:
        model = client.models.retrieve(model_id)
        return model.model_dump()
    except APIStatusError as e:
        raise Exception(f"HTTP {e.response.status_code} {e.message}")
    except Exception as e:
        raise Exception(f"获取模型详情失败: {e}")


def stream_chat(
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict],
    params: Optional[dict] = None,
    stop_check: Optional[Callable[[], bool]] = None,
    timeout: int = 60,
    api_type: str = "openai",
    on_reasoning: Optional[Callable[[str], None]] = None,
    on_usage: Optional[Callable[[dict], None]] = None,
) -> Generator[str, None, None]:
    """流式调用 chat API

    使用 openai 官方 SDK 处理流式 SSE 解析。对于 Anthropic 格式，
    因 SDK 不兼容，保留手动 SSE 解析。

    Args:
        base_url:      API 基础地址
        api_key:       API Key
        model:         模型 ID
        messages:      消息列表 [{"role": ..., "content": ...}, ...]
        params:        可选参数字典 (temperature, max_tokens, top_p)
        stop_check:    可选停止检查函数，返回 True 时中断
        timeout:       超时秒数
        api_type:      API 格式类型
        on_reasoning:  可选推理内容回调，每次收到 reasoning_content 时调用
        on_usage:      可选 token 用量回调，收到 usage 时调用

    Yields:
        每次返回一个文本块（content delta）
    """
    # ── Anthropic 特殊处理（openai SDK 不兼容） ──
    if api_type == "anthropic":
        yield from stream_chat_anthropic(
            base_url, api_key, model, messages,
            params, stop_check, timeout, on_reasoning, on_usage,
        )
        return

    # ── OpenAI 兼容格式（使用 openai SDK） ──
    client = create_client(base_url, api_key, api_type)

    # 构建请求参数
    kwargs: dict = {
        "model": model,
        "messages": messages,
        "stream": True,
        "timeout": timeout,
        "stream_options": {"include_usage": True},
    }
    if params:
        for key in ("temperature", "max_tokens", "top_p"):
            if key in params and params[key] is not None:
                kwargs[key] = params[key]

    # 发起请求
    try:
        stream = client.chat.completions.create(**kwargs)
    except APIStatusError as e:
        raise Exception(f"HTTP {e.response.status_code} {e.message}\n{e.body}")
    except APIConnectionError as e:
        raise Exception(f"连接失败: {e}")
    except Exception as e:
        raise Exception(str(e))

    # 流式读取
    try:
        for chunk in stream:
            # 停止检查
            if stop_check and stop_check():
                stream.close()
                return

            # 推理内容（DeepSeek R1 等模型，通过额外字段传递）
            if chunk.choices:
                delta = chunk.choices[0].delta
                reasoning = getattr(delta, "reasoning_content", None)
                if reasoning and on_reasoning:
                    on_reasoning(reasoning)

                # 文本内容
                if delta.content:
                    yield delta.content

            # token 用量（最后一个 chunk）
            if chunk.usage and on_usage:
                on_usage({
                    "prompt_tokens": chunk.usage.prompt_tokens or 0,
                    "completion_tokens": chunk.usage.completion_tokens or 0,
                })
    finally:
        stream.close()


# ── Backward-compat aliases ──
_create_client = create_client
_parse_anthropic_stream = parse_anthropic_stream
_anthropic_headers = anthropic_headers
_anthropic_chat_url = anthropic_chat_url
_anthropic_chat_body = anthropic_chat_body
