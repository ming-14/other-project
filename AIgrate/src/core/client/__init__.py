"""API 客户端子包

提供多格式 API 客户端封装，支持 OpenAI、Azure、Anthropic、HuggingFace。
"""

from core.client.chat import test_connection, fetch_models, fetch_model_detail, stream_chat

__all__ = [
    "test_connection",
    "fetch_models",
    "fetch_model_detail",
    "stream_chat",
]