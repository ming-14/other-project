import pytest
from io import StringIO
from unittest.mock import patch
from core.models import AIPool, ApiKeyConfig, ModelOverride, ErrorConfig
from core.pool.router import PoolRouter
from cli.printer.format import info, success, error, warning, system, dim, header, divider, bold, ai, user
from cli.printer.route_status import route_status
from cli.printer.help_text import welcome, print_help
from cli.printer.pool_display import print_pools, print_pool_detail


def _make_pool_and_router():
    pool = AIPool(
        name="test-pool",
        keys=[
            ApiKeyConfig(
                base_url="https://api1.example.com/v1",
                api_key="sk-key1",
                label="Key1",
                errors=ErrorConfig(max_concurrency=1, timeout=30, max_errors=3, failure_pause=1),
                models={"model-a": ModelOverride(model_id="model-a")},
            ),
        ],
    )
    router = PoolRouter(pool)
    return pool, router


class TestBasicOutput:
    def test_info(self, capsys):
        info("hello")
        captured = capsys.readouterr()
        assert "hello" in captured.out

    def test_success(self, capsys):
        success("done")
        captured = capsys.readouterr()
        assert "done" in captured.out

    def test_error(self, capsys):
        error("fail")
        captured = capsys.readouterr()
        assert "fail" in captured.err

    def test_warning(self, capsys):
        warning("warn")
        captured = capsys.readouterr()
        assert "warn" in captured.out

    def test_system(self, capsys):
        system("sys")
        captured = capsys.readouterr()
        assert "sys" in captured.out

    def test_user(self, capsys):
        user("msg")
        captured = capsys.readouterr()
        assert "msg" in captured.out

    def test_dim(self, capsys):
        dim("dim text")
        captured = capsys.readouterr()
        assert "dim text" in captured.out

    def test_ai_no_newline(self, capsys):
        ai("partial")
        captured = capsys.readouterr()
        assert "partial" in captured.out

    def test_header(self, capsys):
        header("Title")
        captured = capsys.readouterr()
        assert "Title" in captured.out
        assert "---" in captured.out

    def test_divider(self, capsys):
        divider()
        captured = capsys.readouterr()
        assert "-" in captured.out

    def test_bold_returns_text(self):
        assert bold("text") == "text"


class TestRouteStatus:
    def test_route_status_shows_available(self, capsys):
        pool, router = _make_pool_and_router()
        route_status(pool, router)
        captured = capsys.readouterr()
        assert "test-pool" in captured.out
        assert "model-a" in captured.out
        assert "可用" in captured.out

    def test_route_status_shows_disabled(self, capsys):
        pool, router = _make_pool_and_router()
        ki, mid, kc, mo = router.select_entry()
        router.report_error(ki, mid, kc)
        router.report_error(ki, mid, kc)
        router.report_error(ki, mid, kc)
        route_status(pool, router)
        captured = capsys.readouterr()
        assert "禁用" in captured.out


class TestWelcome:
    def test_welcome_output(self, capsys):
        welcome()
        captured = capsys.readouterr()
        assert "AI 池" in captured.out
        assert "/help" in captured.out


class TestPrintHelp:
    def test_help_output(self, capsys):
        print_help()
        captured = capsys.readouterr()
        assert "/connect" in captured.out
        assert "/pool" in captured.out
        assert "/help" in captured.out
        assert "/exit" in captured.out


class TestPrintPools:
    def test_print_pools_with_names(self, capsys):
        print_pools(["pool1", "pool2"])
        captured = capsys.readouterr()
        assert "pool1" in captured.out
        assert "pool2" in captured.out

    def test_print_pools_empty(self, capsys):
        print_pools([])
        captured = capsys.readouterr()
        assert "暂无" in captured.out


class TestPrintPoolDetail:
    def test_pool_detail_output(self, capsys):
        pool, _ = _make_pool_and_router()
        print_pool_detail(pool)
        captured = capsys.readouterr()
        assert "test-pool" in captured.out
        assert "Key1" in captured.out
        assert "model-a" in captured.out