"""API 客户端测试 - 基于 openai SDK 版本"""

import json
import pytest
from unittest.mock import patch, MagicMock, ANY

from openai.types.chat import ChatCompletionChunk
from openai.types.chat.chat_completion_chunk import Choice, ChoiceDelta
from openai.types.completion_usage import CompletionUsage

from core.client import chat as api_client


# ======================================================================
# 辅助：构建 mock chunk
# ======================================================================

def _make_chunk(
    content: str = "",
    reasoning: str = "",
    finish_reason: str | None = None,
    usage: CompletionUsage | None = None,
) -> ChatCompletionChunk:
    """构造一个 ChatCompletionChunk 用于测试"""
    return ChatCompletionChunk(
        id="chunk_test",
        choices=[
            Choice(
                delta=ChoiceDelta(
                    content=content or None,
                    reasoning_content=reasoning or None,
                ),
                index=0,
                finish_reason=finish_reason,
            )
        ],
        created=1234567890,
        model="test-model",
        object="chat.completion.chunk",
        usage=usage,
    )


def _mock_stream(*chunks):
    """创建一个模拟的流式响应迭代器"""
    class MockStream:
        def __init__(self, items):
            self._items = list(items)
            self._idx = 0
            self._closed = False

        def __iter__(self):
            return self

        def __next__(self):
            if self._closed or self._idx >= len(self._items):
                raise StopIteration
            val = self._items[self._idx]
            self._idx += 1
            return val

        def close(self):
            self._closed = True

    return MockStream(chunks)


def _make_mock_client():
    """创建一个模拟的 OpenAI 客户端"""
    client = MagicMock()
    client.models.list.return_value = [
        MagicMock(id="gpt-4", model_dump=lambda: {"id": "gpt-4", "object": "model"}),
        MagicMock(id="gpt-3.5-turbo", model_dump=lambda: {"id": "gpt-3.5-turbo", "object": "model"}),
    ]
    client.models.retrieve.return_value = MagicMock(
        id="gpt-4",
        model_dump=lambda: {"id": "gpt-4", "owned_by": "openai"},
    )
    return client


# ======================================================================
# test_connection
# ======================================================================

class TestTestConnection:
    @patch("core.client.chat.create_client")
    def test_success(self, mock_create):
        mock_create.return_value = _make_mock_client()
        result = api_client.test_connection("https://api.test.com/v1", "sk-test")
        assert result is True
        mock_create.assert_called_once_with("https://api.test.com/v1", "sk-test", "openai")

    @patch("core.client.chat.create_client")
    def test_http_error(self, mock_create):
        from openai import AuthenticationError
        import httpx
        client = MagicMock()
        client.models.list.side_effect = AuthenticationError(
            message="Unauthorized",
            response=httpx.Response(401, request=httpx.Request("GET", "http://test.com")),
            body={"error": "unauthorized"},
        )
        mock_create.return_value = client
        with pytest.raises(Exception, match="HTTP 401"):
            api_client.test_connection("https://api.test.com/v1", "sk-bad")

    @patch("core.client.chat.create_client")
    def test_connection_error(self, mock_create):
        from openai import APIConnectionError
        import httpx
        client = MagicMock()
        client.models.list.side_effect = APIConnectionError(
            message="refused",
            request=httpx.Request("GET", "http://test.com"),
        )
        mock_create.return_value = client
        with pytest.raises(Exception, match="连接测试失败"):
            api_client.test_connection("https://api.test.com/v1", "sk-test")

    # ── Anthropic（保留手动） ──

    @patch("core.client.chat.urlopen")
    def test_anthropic_success(self, mock_urlopen):
        resp = MagicMock()
        resp.read.return_value = json.dumps({"data": []}).encode()
        mock_urlopen.return_value = resp
        result = api_client.test_connection(
            "https://api.anthropic.com/v1", "sk-ant", api_type="anthropic",
        )
        assert result is True

    @patch("core.client.chat.urlopen")
    def test_anthropic_http_error(self, mock_urlopen):
        error_resp = MagicMock()
        error_resp.read.return_value = b"error body"
        error_resp.code = 401
        error_resp.reason = "Unauthorized"
        from urllib.error import HTTPError
        mock_urlopen.side_effect = HTTPError(
            "https://api.anthropic.com/v1/models", 401, "Unauthorized", {}, error_resp,
        )
        with pytest.raises(Exception, match="HTTP 401"):
            api_client.test_connection(
                "https://api.anthropic.com/v1", "sk-bad", api_type="anthropic",
            )


# ======================================================================
# fetch_models
# ======================================================================

class TestFetchModels:
    @patch("core.client.chat.create_client")
    def test_success(self, mock_create):
        mock_create.return_value = _make_mock_client()
        ids, details = api_client.fetch_models("https://api.test.com/v1", "sk-test")
        assert ids == ["gpt-4", "gpt-3.5-turbo"]
        assert "gpt-4" in details
        assert details["gpt-4"]["id"] == "gpt-4"

    @patch("core.client.chat.create_client")
    def test_empty_list(self, mock_create):
        client = MagicMock()
        client.models.list.return_value = []
        mock_create.return_value = client
        ids, details = api_client.fetch_models("https://api.test.com/v1", "sk-test")
        assert ids == []
        assert details == {}

    @patch("core.client.chat.create_client")
    def test_http_error(self, mock_create):
        from openai import PermissionDeniedError
        import httpx
        client = MagicMock()
        client.models.list.side_effect = PermissionDeniedError(
            message="Forbidden",
            response=httpx.Response(403, request=httpx.Request("GET", "http://test.com")),
            body={"error": "forbidden"},
        )
        mock_create.return_value = client
        with pytest.raises(Exception, match="HTTP 403"):
            api_client.fetch_models("https://api.test.com/v1", "sk-test")

    @patch("core.client.chat.create_client")
    def test_azure_fetch(self, mock_create):
        mock_create.return_value = _make_mock_client()
        ids, details = api_client.fetch_models(
            "https://my.openai.azure.com", "azure-key", api_type="azure",
        )
        assert "gpt-4" in ids
        mock_create.assert_called_once_with(
            "https://my.openai.azure.com", "azure-key", "azure",
        )

    @patch("core.client.chat.urlopen")
    def test_anthropic_fetch(self, mock_urlopen):
        data = {"data": [{"id": "claude-3-opus"}, {"id": "claude-3-sonnet"}]}
        resp = MagicMock()
        resp.read.return_value = json.dumps(data).encode()
        mock_urlopen.return_value = resp
        ids, details = api_client.fetch_models(
            "https://api.anthropic.com/v1", "sk-ant", api_type="anthropic",
        )
        assert "claude-3-opus" in ids


# ======================================================================
# fetch_model_detail
# ======================================================================

class TestFetchModelDetail:
    @patch("core.client.chat.create_client")
    def test_success(self, mock_create):
        mock_create.return_value = _make_mock_client()
        result = api_client.fetch_model_detail(
            "https://api.test.com/v1", "sk-test", "gpt-4",
        )
        assert result["id"] == "gpt-4"
        assert result["owned_by"] == "openai"

    @patch("core.client.chat.create_client")
    def test_http_error(self, mock_create):
        from openai import NotFoundError
        import httpx
        client = MagicMock()
        client.models.retrieve.side_effect = NotFoundError(
            message="Not Found",
            response=httpx.Response(404, request=httpx.Request("GET", "http://test.com")),
            body={"error": "not found"},
        )
        mock_create.return_value = client
        with pytest.raises(Exception, match="HTTP 404"):
            api_client.fetch_model_detail(
                "https://api.test.com/v1", "sk-test", "gpt-4",
            )

    @patch("core.client.chat.urlopen")
    def test_anthropic_detail(self, mock_urlopen):
        data = {"id": "claude-3-opus", "owned_by": "anthropic"}
        resp = MagicMock()
        resp.read.return_value = json.dumps(data).encode()
        mock_urlopen.return_value = resp
        result = api_client.fetch_model_detail(
            "https://api.anthropic.com/v1", "sk-ant", "claude-3-opus",
            api_type="anthropic",
        )
        assert result["id"] == "claude-3-opus"


# ======================================================================
# stream_chat
# ======================================================================

class TestStreamChat:
    @patch("core.client.chat.create_client")
    def test_stream_yields_content(self, mock_create):
        client = MagicMock()
        client.chat.completions.create.return_value = _mock_stream(
            _make_chunk(content="Hello"),
            _make_chunk(content=" World"),
            _make_chunk(content="", finish_reason="stop"),
        )
        mock_create.return_value = client

        chunks = list(api_client.stream_chat(
            "https://api.test.com/v1", "sk-test", "gpt-4",
            [{"role": "user", "content": "hi"}],
        ))
        assert chunks == ["Hello", " World"]

    @patch("core.client.chat.create_client")
    def test_with_params(self, mock_create):
        client = MagicMock()
        client.chat.completions.create.return_value = _mock_stream(
            _make_chunk(content="ok", finish_reason="stop"),
        )
        mock_create.return_value = client

        chunks = list(api_client.stream_chat(
            "https://api.test.com/v1", "sk-test", "gpt-4",
            [{"role": "user", "content": "hi"}],
            params={"temperature": 0.5, "max_tokens": 100},
        ))
        assert chunks == ["ok"]

        # 验证参数传递
        _, kwargs = client.chat.completions.create.call_args
        assert kwargs["temperature"] == 0.5
        assert kwargs["max_tokens"] == 100
        assert kwargs["stream"] is True
        assert kwargs["stream_options"] == {"include_usage": True}

    @patch("core.client.chat.create_client")
    def test_http_error(self, mock_create):
        from openai import RateLimitError
        import httpx
        client = MagicMock()
        client.chat.completions.create.side_effect = RateLimitError(
            message="Rate Limited",
            response=httpx.Response(429, request=httpx.Request("GET", "http://test.com")),
            body={"error": "rate limit"},
        )
        mock_create.return_value = client

        with pytest.raises(Exception, match="HTTP 429"):
            list(api_client.stream_chat(
                "https://api.test.com/v1", "sk-test", "gpt-4",
                [{"role": "user", "content": "hi"}],
            ))

    @patch("core.client.chat.create_client")
    def test_stop_check(self, mock_create):
        client = MagicMock()
        client.chat.completions.create.return_value = _mock_stream(
            _make_chunk(content="chunk1"),
            _make_chunk(content="chunk2"),
            _make_chunk(content="chunk3"),
        )
        mock_create.return_value = client

        stop_after = [False]
        def stop_check():
            if stop_after[0]:
                return True
            stop_after[0] = True
            return False

        chunks = list(api_client.stream_chat(
            "https://api.test.com/v1", "sk-test", "gpt-4",
            [{"role": "user", "content": "hi"}],
            stop_check=stop_check,
        ))
        assert len(chunks) == 1  # 只收到了第一个 chunk 后就停止了

    @patch("core.client.chat.create_client")
    def test_reasoning_content(self, mock_create):
        client = MagicMock()
        client.chat.completions.create.return_value = _mock_stream(
            _make_chunk(reasoning="thinking..."),
            _make_chunk(content="answer"),
            _make_chunk(content="", finish_reason="stop"),
        )
        mock_create.return_value = client

        reasoning_parts = []
        def on_reasoning(text):
            reasoning_parts.append(text)

        chunks = list(api_client.stream_chat(
            "https://api.test.com/v1", "sk-test", "deepseek-r1",
            [{"role": "user", "content": "hi"}],
            on_reasoning=on_reasoning,
        ))
        assert reasoning_parts == ["thinking..."]
        assert chunks == ["answer"]

    @patch("core.client.chat.create_client")
    def test_usage_callback(self, mock_create):
        usage = CompletionUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30)
        client = MagicMock()
        client.chat.completions.create.return_value = _mock_stream(
            _make_chunk(content="done", finish_reason="stop", usage=usage),
        )
        mock_create.return_value = client

        usage_data = []
        def on_usage(u):
            usage_data.append(u)

        list(api_client.stream_chat(
            "https://api.test.com/v1", "sk-test", "gpt-4",
            [{"role": "user", "content": "hi"}],
            on_usage=on_usage,
        ))
        assert len(usage_data) == 1
        assert usage_data[0]["prompt_tokens"] == 10
        assert usage_data[0]["completion_tokens"] == 20

    @patch("core.client.chat.create_client")
    def test_azure_stream(self, mock_create):
        client = MagicMock()
        client.chat.completions.create.return_value = _mock_stream(
            _make_chunk(content="Azure"),
            _make_chunk(content="", finish_reason="stop"),
        )
        mock_create.return_value = client

        chunks = list(api_client.stream_chat(
            "https://my-resource.openai.azure.com/openai/deployments/deploy1",
            "azure-key", "gpt-4",
            [{"role": "user", "content": "hi"}],
            api_type="azure",
        ))
        assert chunks == ["Azure"]
        mock_create.assert_called_once_with(
            "https://my-resource.openai.azure.com/openai/deployments/deploy1",
            "azure-key", "azure",
        )

    @patch("core.client.chat.create_client")
    def test_huggingface_stream(self, mock_create):
        client = MagicMock()
        client.chat.completions.create.return_value = _mock_stream(
            _make_chunk(content="HF", finish_reason="stop"),
        )
        mock_create.return_value = client

        chunks = list(api_client.stream_chat(
            "https://my-model.us-east-1.aws.endpoints.huggingface.cloud",
            "hf_token", "mistral",
            [{"role": "user", "content": "hi"}],
            api_type="huggingface",
        ))
        assert chunks == ["HF"]
        mock_create.assert_called_once_with(
            "https://my-model.us-east-1.aws.endpoints.huggingface.cloud",
            "hf_token", "huggingface",
        )


# ======================================================================
# Anthropic 流式测试（保留手动处理）
# ======================================================================

class TestStreamChatAnthropic:
    @patch("core.client.anthropic.urlopen")
    def test_anthropic_stream(self, mock_urlopen):
        sse_data = (
            b"data: {\"type\":\"content_block_delta\",\"delta\":{\"text\":\"Hello\"}}\n\n"
            b"data: {\"type\":\"content_block_delta\",\"delta\":{\"text\":\" Claude\"}}\n\n"
            b"data: {\"type\":\"message_stop\"}\n\n"
        )
        resp = MagicMock()
        resp.__iter__ = MagicMock(return_value=iter([sse_data]))
        resp.close = MagicMock()
        mock_urlopen.return_value = resp

        chunks = list(api_client.stream_chat(
            "https://api.anthropic.com/v1", "sk-ant-key", "claude-3",
            [{"role": "user", "content": "hi"}],
            api_type="anthropic",
        ))
        assert chunks == ["Hello", " Claude"]

    @patch("core.client.anthropic.urlopen")
    def test_anthropic_system_prompt(self, mock_urlopen):
        sse_data = (
            b"data: {\"type\":\"content_block_delta\",\"delta\":{\"text\":\"ok\"}}\n\n"
            b"data: {\"type\":\"message_stop\"}\n\n"
        )
        resp = MagicMock()
        resp.__iter__ = MagicMock(return_value=iter([sse_data]))
        resp.close = MagicMock()
        mock_urlopen.return_value = resp

        list(api_client.stream_chat(
            "https://api.anthropic.com/v1", "sk-ant-key", "claude-3",
            [
                {"role": "system", "content": "Be helpful"},
                {"role": "user", "content": "hi"},
            ],
            api_type="anthropic",
        ))

        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        body = json.loads(req.data)
        assert body["system"] == "Be helpful"
        assert body["messages"] == [{"role": "user", "content": "hi"}]

    @patch("core.client.anthropic.urlopen")
    def test_anthropic_http_error(self, mock_urlopen):
        error_resp = MagicMock()
        error_resp.read.return_value = b"rate limited"
        error_resp.code = 429
        error_resp.reason = "Too Many Requests"
        from urllib.error import HTTPError
        mock_urlopen.side_effect = HTTPError(
            "https://api.anthropic.com/v1/messages", 429, "Too Many Requests", {}, error_resp,
        )
        with pytest.raises(Exception, match="HTTP 429"):
            list(api_client.stream_chat(
                "https://api.anthropic.com/v1", "sk-ant-key", "claude-3",
                [{"role": "user", "content": "hi"}],
                api_type="anthropic",
            ))


# ======================================================================
# Anthropic 内部辅助函数
# ======================================================================

class TestAnthropicHelpers:
    def test_anthropic_headers(self):
        h = api_client._anthropic_headers("sk-ant")
        assert h["x-api-key"] == "sk-ant"
        assert h["anthropic-version"] == "2023-06-01"
        assert "Authorization" not in h

    def test_anthropic_chat_url(self):
        url = api_client._anthropic_chat_url("https://api.anthropic.com/v1")
        assert url == "https://api.anthropic.com/v1/messages"

    def test_anthropic_chat_body_basic(self):
        body = api_client._anthropic_chat_body(
            "claude-3", [{"role": "user", "content": "hi"}],
        )
        assert body["model"] == "claude-3"
        assert body["stream"] is True
        assert body["messages"] == [{"role": "user", "content": "hi"}]
        assert "system" not in body

    def test_anthropic_chat_body_with_system(self):
        msgs = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "hi"},
        ]
        body = api_client._anthropic_chat_body("claude-3", msgs)
        assert body["system"] == "You are helpful"
        assert body["messages"] == [{"role": "user", "content": "hi"}]

    def test_anthropic_chat_body_with_params(self):
        body = api_client._anthropic_chat_body(
            "claude-3", [{"role": "user", "content": "hi"}],
            params={"temperature": 0.7, "max_tokens": 2048, "top_p": 0.9},
        )
        assert body["max_tokens"] == 2048
        assert body["temperature"] == 0.7
        assert body["top_p"] == 0.9

    def test_parse_anthropic_stream_content(self):
        data = '{"type":"content_block_delta","delta":{"text":"world"}}'
        content, reasoning, usage = api_client._parse_anthropic_stream(data)
        assert content == "world"

    def test_parse_anthropic_stream_stop(self):
        data = '{"type":"message_stop"}'
        content, reasoning, usage = api_client._parse_anthropic_stream(data)
        assert content is None

    def test_parse_anthropic_stream_other(self):
        data = '{"type":"message_start","message":{"id":"msg_123"}}'
        content, reasoning, usage = api_client._parse_anthropic_stream(data)
        assert content == ""

    def test_parse_anthropic_stream_invalid(self):
        content, _, _ = api_client._parse_anthropic_stream("not json")
        assert content == ""


# ======================================================================
# 客户端创建
# ======================================================================

class TestCreateClient:
    def test_openai_client(self):
        client = api_client._create_client("https://api.test.com/v1", "sk-test")
        from openai import OpenAI
        assert isinstance(client, OpenAI)
        assert client.api_key == "sk-test"
        assert str(client.base_url).rstrip("/") == "https://api.test.com/v1"

    def test_azure_client(self):
        client = api_client._create_client(
            "https://my-resource.openai.azure.com", "azure-key", "azure",
        )
        from openai import AzureOpenAI
        assert isinstance(client, AzureOpenAI)