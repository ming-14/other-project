import os
import sys
import pytest
import tempfile
import json

_src = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

from core.models import (
    LimitRule, ErrorConfig, ModelOverride, ApiKeyConfig, AIPool, SingleAI, ChatParams,
)


@pytest.fixture
def sample_limit_rule_time():
    return LimitRule(type="time_per_req", time=5)


@pytest.fixture
def sample_limit_rule_count():
    return LimitRule(type="count_per_time", time=60, count=10)


@pytest.fixture
def sample_limit_rule_tokens():
    return LimitRule(type="tokens_per_time", time=60, tokens=1000)


@pytest.fixture
def sample_error_config():
    return ErrorConfig(max_concurrency=2, timeout=30, max_errors=3, failure_pause=40)


@pytest.fixture
def sample_model_override():
    return ModelOverride(
        model_id="gpt-4",
        context_length=8192,
        max_concurrency=3,
        timeout=60,
        max_errors=5,
        max_requests=100,
        failure_pause=30,
        rate_limits=[LimitRule(type="count_per_time", time=60, count=20)],
    )


@pytest.fixture
def sample_api_key_config():
    return ApiKeyConfig(
        base_url="https://api.example.com/v1",
        api_key="sk-test123456",
        type="openai",
        label="TestKey",
        max_requests=50,
        errors=ErrorConfig(max_concurrency=1, timeout=30, max_errors=3, failure_pause=40),
        rate_limits=[LimitRule(type="time_per_req", time=2)],
        models={
            "gpt-4": ModelOverride(model_id="gpt-4"),
            "gpt-3.5-turbo": ModelOverride(model_id="gpt-3.5-turbo"),
        },
    )


@pytest.fixture
def sample_pool():
    return AIPool(
        name="test-pool",
        keys=[
            ApiKeyConfig(
                base_url="https://api1.example.com/v1",
                api_key="sk-key1",
                label="Key1",
                errors=ErrorConfig(max_concurrency=1, timeout=30, max_errors=3, failure_pause=1),
                models={"model-a": ModelOverride(model_id="model-a")},
            ),
            ApiKeyConfig(
                base_url="https://api2.example.com/v1",
                api_key="sk-key2",
                label="Key2",
                errors=ErrorConfig(max_concurrency=1, timeout=30, max_errors=3, failure_pause=1),
                models={"model-b": ModelOverride(model_id="model-b")},
            ),
        ],
    )


@pytest.fixture
def tmp_data_dir(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return data_dir


@pytest.fixture
def sample_single_ai():
    return SingleAI(
        name="test-ai",
        alias="tai",
        key=ApiKeyConfig(
            base_url="https://api.example.com/v1",
            api_key="sk-test123456",
            type="openai",
            label="TestAI",
            errors=ErrorConfig(max_concurrency=1, timeout=30, max_errors=3, failure_pause=40),
        ),
        models={
            "gpt-4": ModelOverride(model_id="gpt-4"),
            "gpt-3.5-turbo": ModelOverride(model_id="gpt-3.5-turbo"),
        },
    )


@pytest.fixture
def chat_params():
    return ChatParams()