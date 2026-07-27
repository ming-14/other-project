import pytest
from core.models import (
    LimitRule, ErrorConfig, ModelOverride, ApiKeyConfig, AIPool, SingleAI, ChatParams,
    VALID_API_TYPES,
)


class TestLimitRule:
    def test_describe_time_per_req(self, sample_limit_rule_time):
        assert sample_limit_rule_time.describe() == "5s/次"

    def test_describe_count_per_time(self, sample_limit_rule_count):
        assert sample_limit_rule_count.describe() == "10次/60s"

    def test_describe_tokens_per_time(self, sample_limit_rule_tokens):
        assert sample_limit_rule_tokens.describe() == "1000token/60s"

    def test_describe_unknown_type(self):
        rule = LimitRule(type="unknown", time=10)
        result = rule.describe()
        assert "unknown" in result or "LimitRule" in result

    def test_to_dict_minimal(self):
        rule = LimitRule(type="time_per_req", time=5)
        d = rule.to_dict()
        assert d == {"type": "time_per_req", "time": 5}
        assert "count" not in d
        assert "tokens" not in d

    def test_to_dict_with_count(self):
        rule = LimitRule(type="count_per_time", time=60, count=10)
        d = rule.to_dict()
        assert d == {"type": "count_per_time", "time": 60, "count": 10}

    def test_to_dict_with_tokens(self):
        rule = LimitRule(type="tokens_per_time", time=60, tokens=1000)
        d = rule.to_dict()
        assert d == {"type": "tokens_per_time", "time": 60, "tokens": 1000}

    def test_from_dict_minimal(self):
        data = {"type": "time_per_req", "time": 5}
        rule = LimitRule.from_dict(data)
        assert rule.type == "time_per_req"
        assert rule.time == 5
        assert rule.count is None
        assert rule.tokens is None

    def test_from_dict_full(self):
        data = {"type": "count_per_time", "time": 60, "count": 10, "tokens": 500}
        rule = LimitRule.from_dict(data)
        assert rule.type == "count_per_time"
        assert rule.time == 60
        assert rule.count == 10
        assert rule.tokens == 500

    def test_roundtrip(self):
        original = LimitRule(type="tokens_per_time", time=120, tokens=5000)
        restored = LimitRule.from_dict(original.to_dict())
        assert restored.type == original.type
        assert restored.time == original.time
        assert restored.tokens == original.tokens


class TestErrorConfig:
    def test_default_values(self):
        ec = ErrorConfig()
        assert ec.max_concurrency is None
        assert ec.timeout is None
        assert ec.max_errors is None
        assert ec.failure_pause is None
        assert ec.max_errors_model is None
        assert ec.failure_pause_model is None

    def test_to_dict(self, sample_error_config):
        d = sample_error_config.to_dict()
        assert d == {
            "max_concurrency": 2,
            "timeout": 30,
            "max_errors": 3,
            "failure_pause": 40,
        }

    def test_to_dict_with_new_fields(self):
        ec = ErrorConfig(max_errors_model=5, failure_pause_model=20)
        d = ec.to_dict()
        assert d["max_errors_model"] == 5
        assert d["failure_pause_model"] == 20

    def test_to_dict_omits_none_new_fields(self):
        ec = ErrorConfig()
        d = ec.to_dict()
        assert "max_errors_model" not in d
        assert "failure_pause_model" not in d

    def test_from_dict_none(self):
        ec = ErrorConfig.from_dict(None)
        assert ec.max_concurrency is None
        assert ec.max_errors_model is None
        assert ec.failure_pause_model is None

    def test_from_dict_empty(self):
        ec = ErrorConfig.from_dict({})
        assert ec.max_concurrency is None
        assert ec.max_errors_model is None
        assert ec.failure_pause_model is None

    def test_from_dict_full(self, sample_error_config):
        d = sample_error_config.to_dict()
        ec = ErrorConfig.from_dict(d)
        assert ec.max_concurrency == 2
        assert ec.timeout == 30
        assert ec.max_errors == 3
        assert ec.failure_pause == 40

    def test_from_dict_with_new_fields(self):
        data = {"max_errors_model": 5, "failure_pause_model": 20}
        ec = ErrorConfig.from_dict(data)
        assert ec.max_errors_model == 5
        assert ec.failure_pause_model == 20

    def test_roundtrip(self, sample_error_config):
        restored = ErrorConfig.from_dict(sample_error_config.to_dict())
        assert restored.max_concurrency == sample_error_config.max_concurrency
        assert restored.timeout == sample_error_config.timeout
        assert restored.max_errors == sample_error_config.max_errors
        assert restored.failure_pause == sample_error_config.failure_pause


class TestModelOverride:
    def test_default_values(self):
        mo = ModelOverride(model_id="test-model")
        assert mo.model_id == "test-model"
        assert mo.groups == ["other"]
        assert mo.context_length is None
        assert mo.max_concurrency is None
        assert mo.timeout is None
        assert mo.max_errors is None
        assert mo.max_requests is None
        assert mo.failure_pause is None
        assert mo.rate_limits == []

    def test_to_dict(self, sample_model_override):
        d = sample_model_override.to_dict()
        assert d["model_id"] == "gpt-4"
        assert d["context-length"] == 8192
        assert d["errors"]["max_concurrency"] == 3
        assert d["errors"]["timeout"] == 60
        assert d["errors"]["max_errors"] == 5
        assert d["errors"]["failure_pause"] == 30
        assert d["max_requests"] == 100
        assert len(d["rate_limits"]) == 1
        assert d["rate_limits"][0]["type"] == "count_per_time"

    def test_to_dict_no_optional(self):
        mo = ModelOverride(model_id="minimal")
        d = mo.to_dict()
        assert "context-length" not in d
        assert "max_requests" not in d
        assert "groups" not in d  # ["other"] 不输出
        assert d["errors"]["max_concurrency"] is None
        assert d["rate_limits"] == []

    def test_to_dict_custom_groups(self):
        mo = ModelOverride(model_id="m1", groups=["free", "cn"])
        d = mo.to_dict()
        assert d["groups"] == ["free", "cn"]

    def test_from_dict_with_groups(self):
        data = {"model_id": "m1", "groups": ["premium", "eu"]}
        mo = ModelOverride.from_dict(data)
        assert mo.groups == ["premium", "eu"]

    def test_from_dict_no_groups_defaults_other(self):
        data = {"model_id": "m1"}
        mo = ModelOverride.from_dict(data)
        assert mo.groups == ["other"]

    def test_from_dict(self, sample_model_override):
        d = sample_model_override.to_dict()
        mo = ModelOverride.from_dict(d)
        assert mo.model_id == "gpt-4"
        assert mo.context_length == 8192
        assert mo.max_concurrency == 3
        assert mo.timeout == 60
        assert mo.max_errors == 5
        assert mo.max_requests == 100
        assert mo.failure_pause == 30
        assert len(mo.rate_limits) == 1
        assert mo.rate_limits[0].type == "count_per_time"

    def test_from_dict_empty_errors(self):
        data = {"model_id": "test"}
        mo = ModelOverride.from_dict(data)
        assert mo.model_id == "test"
        assert mo.max_concurrency is None
        assert mo.rate_limits == []

    def test_roundtrip(self, sample_model_override):
        d = sample_model_override.to_dict()
        restored = ModelOverride.from_dict(d)
        assert restored.model_id == sample_model_override.model_id
        assert restored.context_length == sample_model_override.context_length
        assert restored.max_concurrency == sample_model_override.max_concurrency
        assert restored.timeout == sample_model_override.timeout
        assert restored.max_errors == sample_model_override.max_errors
        assert restored.max_requests == sample_model_override.max_requests
        assert restored.failure_pause == sample_model_override.failure_pause
        assert len(restored.rate_limits) == len(sample_model_override.rate_limits)


class TestApiKeyConfig:
    def test_default_values(self):
        kc = ApiKeyConfig(base_url="https://api.test.com", api_key="sk-test")
        assert kc.type == "openai"
        assert kc.label == ""
        assert kc.groups == ["other"]
        assert kc.max_requests is None
        assert kc.errors.max_concurrency == 1
        assert kc.errors.timeout == 30
        assert kc.errors.max_errors == 3
        assert kc.errors.failure_pause == 40
        assert kc.rate_limits is None
        assert kc.models == {}

    def test_azure_type(self):
        kc = ApiKeyConfig(base_url="https://my.openai.azure.com", api_key="azure-key", type="azure")
        assert kc.type == "azure"

    def test_anthropic_type(self):
        kc = ApiKeyConfig(base_url="https://api.anthropic.com", api_key="sk-ant", type="anthropic")
        assert kc.type == "anthropic"

    def test_huggingface_type(self):
        kc = ApiKeyConfig(base_url="https://api.hf.cloud", api_key="hf_token", type="huggingface")
        assert kc.type == "huggingface"

    def test_valid_api_types_contains_all(self):
        assert "openai" in VALID_API_TYPES
        assert "azure" in VALID_API_TYPES
        assert "anthropic" in VALID_API_TYPES
        assert "huggingface" in VALID_API_TYPES

    def test_get_model_ids(self, sample_api_key_config):
        ids = sample_api_key_config.get_model_ids()
        assert set(ids) == {"gpt-4", "gpt-3.5-turbo"}

    def test_get_model_ids_empty(self):
        kc = ApiKeyConfig(base_url="https://api.test.com", api_key="sk-test")
        assert kc.get_model_ids() == []

    def test_to_dict(self, sample_api_key_config):
        d = sample_api_key_config.to_dict()
        assert d["type"] == "openai"
        assert d["base_url"] == "https://api.example.com/v1"
        assert d["api_key"] == "sk-test123456"
        assert d["label"] == "TestKey"
        assert d["max_requests"] == 50
        assert d["errors"]["max_concurrency"] == 1
        assert len(d["models"]) == 2
        assert d["rate_limits"] is not None
        assert len(d["rate_limits"]) == 1

    def test_to_dict_no_optional(self):
        kc = ApiKeyConfig(base_url="https://api.test.com", api_key="sk-test")
        d = kc.to_dict()
        assert "max_requests" not in d
        assert "groups" not in d  # ["other"] 不输出
        assert "rate_limits" not in d  # None 时不输出

    def test_to_dict_custom_groups(self):
        kc = ApiKeyConfig(base_url="https://api.test.com", api_key="sk-test", groups=["premium", "eu"])
        d = kc.to_dict()
        assert d["groups"] == ["premium", "eu"]

    def test_from_dict_with_groups(self):
        data = {"base_url": "https://api.test.com", "api_key": "sk-test", "groups": ["free", "cn"]}
        kc = ApiKeyConfig.from_dict(data)
        assert kc.groups == ["free", "cn"]

    def test_from_dict_no_groups_defaults_other(self):
        data = {"base_url": "https://api.test.com", "api_key": "sk-test"}
        kc = ApiKeyConfig.from_dict(data)
        assert kc.groups == ["other"]

    def test_from_dict(self, sample_api_key_config):
        d = sample_api_key_config.to_dict()
        kc = ApiKeyConfig.from_dict(d)
        assert kc.base_url == "https://api.example.com/v1"
        assert kc.api_key == "sk-test123456"
        assert kc.type == "openai"
        assert kc.label == "TestKey"
        assert kc.max_requests == 50
        assert kc.errors.max_concurrency == 1
        assert kc.errors.timeout == 30
        assert len(kc.models) == 2
        assert kc.rate_limits is not None
        assert len(kc.rate_limits) == 1

    def test_from_dict_missing_optional(self):
        data = {
            "base_url": "https://api.test.com",
            "api_key": "sk-test",
        }
        kc = ApiKeyConfig.from_dict(data)
        assert kc.type == "openai"
        assert kc.label == ""
        assert kc.max_requests is None

    def test_roundtrip(self, sample_api_key_config):
        d = sample_api_key_config.to_dict()
        restored = ApiKeyConfig.from_dict(d)
        assert restored.base_url == sample_api_key_config.base_url
        assert restored.api_key == sample_api_key_config.api_key
        assert restored.type == sample_api_key_config.type
        assert restored.label == sample_api_key_config.label
        assert restored.max_requests == sample_api_key_config.max_requests
        assert restored.errors.max_concurrency == sample_api_key_config.errors.max_concurrency
        assert len(restored.models) == len(sample_api_key_config.models)


class TestAIPool:
    def test_default_values(self):
        pool = AIPool(name="test")
        assert pool.name == "test"
        assert pool.keys == []

    def test_to_dict(self, sample_pool):
        d = sample_pool.to_dict()
        assert d["name"] == "test-pool"
        assert len(d["keys"]) == 2
        assert d["keys"][0]["label"] == "Key1"

    def test_from_dict(self, sample_pool):
        d = sample_pool.to_dict()
        pool = AIPool.from_dict(d)
        assert pool.name == "test-pool"
        assert len(pool.keys) == 2
        assert pool.keys[0].label == "Key1"
        assert pool.keys[1].label == "Key2"

    def test_from_dict_empty_keys(self):
        data = {"name": "empty-pool"}
        pool = AIPool.from_dict(data)
        assert pool.name == "empty-pool"
        assert pool.keys == []

    def test_roundtrip(self, sample_pool):
        d = sample_pool.to_dict()
        restored = AIPool.from_dict(d)
        assert restored.name == sample_pool.name
        assert len(restored.keys) == len(sample_pool.keys)
        for orig, rest in zip(sample_pool.keys, restored.keys):
            assert orig.base_url == rest.base_url
            assert orig.api_key == rest.api_key
            assert orig.label == rest.label


class TestChatParams:
    def test_default_values(self, chat_params):
        assert chat_params.temperature == 0.7
        assert chat_params.max_tokens == 2048
        assert chat_params.top_p == 1.0
        assert chat_params.system_prompt == ""

    def test_to_dict(self, chat_params):
        d = chat_params.to_dict()
        assert d == {"temperature": 0.7, "max_tokens": 2048, "top_p": 1.0}

    def test_custom_values(self):
        cp = ChatParams(temperature=0.5, max_tokens=1024, top_p=0.9, system_prompt="You are helpful")
        assert cp.temperature == 0.5
        assert cp.max_tokens == 1024
        assert cp.top_p == 0.9
        assert cp.system_prompt == "You are helpful"


class TestSingleAI:
    def test_default_values(self):
        ai = SingleAI(name="test")
        assert ai.name == "test"
        assert ai.alias == ""
        assert ai.models == {}

    def test_get_id_prefers_alias(self, sample_single_ai):
        assert sample_single_ai.get_id() == "tai"

    def test_get_id_falls_back_to_name(self):
        ai = SingleAI(name="my-ai")
        assert ai.get_id() == "my-ai"

    def test_get_model_ids(self, sample_single_ai):
        ids = sample_single_ai.get_model_ids()
        assert ids == ["gpt-4", "gpt-3.5-turbo"]

    def test_get_model_ids_empty(self):
        ai = SingleAI(name="empty")
        assert ai.get_model_ids() == []

    def test_to_dict(self, sample_single_ai):
        d = sample_single_ai.to_dict()
        assert d["type"] == "single"
        assert d["name"] == "test-ai"
        assert d["alias"] == "tai"
        assert "gpt-4" in d["models"]
        assert "gpt-3.5-turbo" in d["models"]
        assert "key" in d

    def test_to_dict_no_alias(self):
        ai = SingleAI(name="no-alias", models={"m1": ModelOverride(model_id="m1")})
        d = ai.to_dict()
        assert "alias" not in d

    def test_from_dict(self, sample_single_ai):
        d = sample_single_ai.to_dict()
        ai = SingleAI.from_dict(d)
        assert ai.name == "test-ai"
        assert ai.alias == "tai"
        assert list(ai.models.keys()) == ["gpt-4", "gpt-3.5-turbo"]
        assert ai.key.base_url == "https://api.example.com/v1"

    def test_from_dict_old_format_models(self):
        data = {
            "name": "old-ai",
            "key": {"base_url": "url", "api_key": "k"},
            "models": [{"model_id": "m1"}, {"model_id": "m2"}],
        }
        ai = SingleAI.from_dict(data)
        assert list(ai.models.keys()) == ["m1", "m2"]

    def test_from_dict_string_models(self):
        data = {
            "name": "str-ai",
            "key": {"base_url": "url", "api_key": "k"},
            "models": ["m1", "m2"],
        }
        ai = SingleAI.from_dict(data)
        assert list(ai.models.keys()) == ["m1", "m2"]
        assert isinstance(ai.models["m1"], ModelOverride)

    def test_roundtrip(self, sample_single_ai):
        d = sample_single_ai.to_dict()
        restored = SingleAI.from_dict(d)
        assert restored.name == sample_single_ai.name
        assert restored.alias == sample_single_ai.alias
        assert list(restored.models.keys()) == list(sample_single_ai.models.keys())
        assert restored.key.base_url == sample_single_ai.key.base_url