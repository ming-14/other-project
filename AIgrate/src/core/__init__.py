"""core 包 - AI 池核心逻辑

提供 AI 池管理、API 客户端封装、模型路由与限速、日志系统、国际化等核心功能。

子包:
  - models:   数据模型定义
  - client:   多格式 API 客户端封装
  - pool:     AI 池管理器、路由器、一键测试与速率限制
  - settings: 应用设置管理器
  - log:      日志系统
  - i18n:     国际化支持
"""

from core.models import (
    VALID_API_TYPES,
    LimitRule,
    ErrorConfig,
    ApiKeyConfig,
    ModelOverride,
    AIPool,
    SingleAI,
    ChatParams,
)
from core.client import test_connection, fetch_models, fetch_model_detail, stream_chat
from core.pool import PoolManager, pool_manager, PoolRouter, test_pool, run_pool_test, RateLimiter
from core.settings import SettingsManager, settings_manager
from core.log import get_logger
from core.i18n import I18nManager, i18n_manager, t

__all__ = [
    # Models
    "VALID_API_TYPES",
    "LimitRule",
    "ErrorConfig",
    "ApiKeyConfig",
    "ModelOverride",
    "AIPool",
    "SingleAI",
    "ChatParams",
    # Client
    "test_connection",
    "fetch_models",
    "fetch_model_detail",
    "stream_chat",
    # Pool
    "PoolManager",
    "pool_manager",
    "PoolRouter",
    "test_pool",
    "run_pool_test",
    "RateLimiter",
    # Settings
    "SettingsManager",
    "settings_manager",
    # Log
    "get_logger",
    # i18n
    "I18nManager",
    "i18n_manager",
    "t",
]