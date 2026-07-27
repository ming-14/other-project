import pytest
from core.models import ApiKeyConfig, ErrorConfig
from cli.pool_editor.helpers import parse_idx, get_key


class TestParseIdx:
    def test_valid_integer(self):
        assert parse_idx("5") == 5

    def test_zero(self):
        assert parse_idx("0") == 0

    def test_negative(self):
        assert parse_idx("-1") == -1

    def test_invalid_string(self, capsys):
        result = parse_idx("abc")
        assert result is None
        captured = capsys.readouterr()
        assert "数字" in captured.err or "数字" in captured.out

    def test_empty_string(self, capsys):
        result = parse_idx("")
        assert result is None

    def test_whitespace_trimmed(self):
        assert parse_idx("  3  ") == 3

    def test_float_string(self, capsys):
        result = parse_idx("1.5")
        assert result is None


class TestGetKey:
    def test_valid_index(self):
        keys = [
            ApiKeyConfig(base_url="url1", api_key="k1", label="A"),
            ApiKeyConfig(base_url="url2", api_key="k2", label="B"),
        ]
        result = get_key(keys, 0)
        assert result.label == "A"

    def test_last_index(self):
        keys = [
            ApiKeyConfig(base_url="url1", api_key="k1", label="A"),
            ApiKeyConfig(base_url="url2", api_key="k2", label="B"),
        ]
        result = get_key(keys, 1)
        assert result.label == "B"

    def test_negative_index(self, capsys):
        keys = [ApiKeyConfig(base_url="url1", api_key="k1")]
        result = get_key(keys, -1)
        assert result is None
        captured = capsys.readouterr()
        assert "越界" in captured.err or "越界" in captured.out

    def test_out_of_range(self, capsys):
        keys = [ApiKeyConfig(base_url="url1", api_key="k1")]
        result = get_key(keys, 5)
        assert result is None

    def test_empty_list(self, capsys):
        result = get_key([], 0)
        assert result is None