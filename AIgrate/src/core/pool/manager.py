"""AI 池管理器

管理 AI 池和普通 AI 的 CRUD，支持 JSON 持久化。
"""

from __future__ import annotations

import json
import os
import threading
from typing import Optional, Callable, Union

from core.models.entities import AIPool, SingleAI
from core.pool.router import PoolRouter
from core.log.logger import get_logger

_logger = get_logger("PoolManager")

_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    "data",
)
POOLS_FILE = os.path.join(_DATA_DIR, "pools.json")

Entry = Union[AIPool, SingleAI]


class PoolManager:
    """管理所有 AI 池和普通 AI，支持 JSON 持久化"""

    def __init__(self):
        self.pools: dict[str, Entry] = {}
        self.routers: dict[str, PoolRouter] = {}
        self._lock = threading.Lock()
        self._on_change_callbacks: list[Callable] = []

    def on_change(self, cb: Callable):
        self._on_change_callbacks.append(cb)

    def _notify_change(self):
        for cb in self._on_change_callbacks:
            try:
                cb()
            except Exception:
                pass

    # ── 查询 ──

    def get_entry(self, name: str) -> Optional[Entry]:
        """获取任意类型的条目"""
        return self.pools.get(name)

    def get_pool(self, name: str) -> Optional[AIPool]:
        """获取池（仅返回 AIPool 类型）"""
        entry = self.pools.get(name)
        if isinstance(entry, AIPool):
            return entry
        return None

    def get_single(self, name: str) -> Optional[SingleAI]:
        """获取普通 AI（仅返回 SingleAI 类型）"""
        entry = self.pools.get(name)
        if isinstance(entry, SingleAI):
            return entry
        return None

    def is_pool(self, name: str) -> bool:
        return isinstance(self.pools.get(name), AIPool)

    def is_single(self, name: str) -> bool:
        return isinstance(self.pools.get(name), SingleAI)

    def get_names(self) -> list[str]:
        """获取所有条目名称"""
        return list(self.pools.keys())

    def get_pool_names(self) -> list[str]:
        """获取池类型名称"""
        return [n for n, e in self.pools.items() if isinstance(e, AIPool)]

    def get_single_names(self) -> list[str]:
        """获取普通 AI 类型名称"""
        return [n for n, e in self.pools.items() if isinstance(e, SingleAI)]

    # ── CRUD ──

    def add_entry(self, entry: Entry):
        """添加任意类型的条目（持久化）"""
        with self._lock:
            self.pools[entry.name] = entry
            if isinstance(entry, AIPool):
                self.routers[entry.name] = PoolRouter(entry)
        self._save()
        self._notify_change()

    def add_temp(self, entry: Entry):
        """添加临时条目（不持久化到 JSON，仅存在于内存）"""
        with self._lock:
            self.pools[entry.name] = entry
            if isinstance(entry, AIPool):
                self.routers[entry.name] = PoolRouter(entry)

    def add_pool(self, pool: AIPool):
        with self._lock:
            self.pools[pool.name] = pool
            self.routers[pool.name] = PoolRouter(pool)
        self._save()
        self._notify_change()

    def remove_entry(self, name: str):
        """删除任意类型的条目"""
        with self._lock:
            self.pools.pop(name, None)
            self.routers.pop(name, None)
        self._save()
        self._notify_change()

    def remove_pool(self, name: str):
        """删除条目（保持向后兼容）"""
        self.remove_entry(name)

    def rename_entry(self, old_name: str, new_name: str) -> bool:
        """重命名任意类型的条目"""
        if new_name in self.pools:
            return False
        with self._lock:
            if old_name not in self.pools:
                return False
            entry = self.pools.pop(old_name)
            entry.name = new_name
            self.pools[new_name] = entry
            router = self.routers.pop(old_name, None)
            if router:
                router.pool = entry
                self.routers[new_name] = router
            elif isinstance(entry, AIPool):
                self.routers[new_name] = PoolRouter(entry)
        self._save()
        self._notify_change()
        return True

    def rename_pool(self, old_name: str, new_name: str) -> bool:
        """重命名（保持向后兼容）"""
        return self.rename_entry(old_name, new_name)

    def update_entry(self, entry: Entry):
        """更新任意类型的条目"""
        with self._lock:
            self.pools[entry.name] = entry
            if isinstance(entry, AIPool):
                if entry.name in self.routers:
                    self.routers[entry.name].pool = entry
                else:
                    self.routers[entry.name] = PoolRouter(entry)
            else:
                self.routers.pop(entry.name, None)
        self._save()
        self._notify_change()

    def update_pool(self, pool: AIPool):
        """更新池（保持向后兼容）"""
        self.update_entry(pool)

    # ── 路由器 ──

    def get_router(self, name: str) -> Optional[PoolRouter]:
        return self.routers.get(name)

    def get_router_for_session(self, pool_name: str) -> Optional[PoolRouter]:
        """获取路由器并重置会话状态"""
        router = self.routers.get(pool_name)
        if router:
            router.reset_session()
        return router

    # ── 组管理代理 ──

    def get_all_groups(self, pool_name: str) -> set:
        """获取指定池的所有组名集合"""
        router = self.routers.get(pool_name)
        if router:
            return router.get_all_groups()
        return set()

    def get_active_groups(self, pool_name: str) -> Optional[set]:
        """获取指定池的当前活跃组集合，None 表示全部活跃"""
        router = self.routers.get(pool_name)
        if router:
            return router.get_active_groups()
        return None

    def set_active_groups(self, pool_name: str, groups: Optional[set]):
        """设置指定池的活跃组集合，None 表示全部活跃"""
        router = self.routers.get(pool_name)
        if router:
            router.set_active_groups(groups)

    # ── 别名解析 ──

    def resolve_model(self, query: str) -> Optional[tuple[str, str, bool]]:
        """
        按别名/名称解析条目。

        返回 (entry_name, first_model_id, is_pool) 或 None。
        优先级：条目名称 > single alias > 模型 ID 原文
        """
        if not query:
            return None

        # 1. 条目名称匹配（池和 single 均可）
        entry = self.pools.get(query)
        if entry:
            if isinstance(entry, AIPool):
                first_mid = ""
                for kc in entry.keys:
                    if kc.models:
                        first_mid = next(iter(kc.models))
                        break
                return (query, first_mid, True)
            else:
                first_mid = next(iter(entry.models)) if entry.models else ""
                return (query, first_mid, False)

        # 2. single alias 匹配
        for name, entry in self.pools.items():
            if isinstance(entry, SingleAI) and entry.alias and entry.alias == query:
                first_mid = next(iter(entry.models)) if entry.models else ""
                return (name, first_mid, False)

        # 3. 模型 ID 原文匹配
        for name, entry in self.pools.items():
            if isinstance(entry, AIPool):
                for kc in entry.keys:
                    if query in kc.models:
                        return (name, query, True)
            else:
                if query in entry.models:
                    return (name, query, False)

        return None

    def get_all_entries_info(self) -> list[dict]:
        """
        获取所有条目的摘要信息。
        """
        result = []
        for name, entry in self.pools.items():
            if isinstance(entry, AIPool):
                model_count = sum(len(kc.models) for kc in entry.keys)
                result.append({
                    "name": name,
                    "enabled": entry.enabled,
                    "is_pool": True,
                    "key_count": len(entry.keys),
                    "model_count": model_count,
                })
            else:
                result.append({
                    "name": name,
                    "alias": entry.alias,
                    "enabled": entry.enabled,
                    "is_pool": False,
                    "model_count": len(entry.models),
                    "label": entry.key.label,
                })
        return result

    # ── 持久化 ──

    def _save(self):
        try:
            os.makedirs(_DATA_DIR, exist_ok=True)
            data = []
            for entry in self.pools.values():
                data.append(entry.to_dict())
            with open(POOLS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            _logger.error("保存失败: %s", e)

    @staticmethod
    def _resolve_templates(data: list[dict]) -> None:
        """解析 JSON 中的内联模板引用（in-place 修改 data）

        模板定义：顶层 type=template 条目，包含 errors/rate_limits 字典。
        引用方式：
          - errors:   {"type": "template", "id": "模板名"}
          - rate_limits: [{"type": "template", "id": "模板名"}, ...]  可与实际规则混合
        """
        templates: dict[str, dict] = {"errors": {}, "rate_limits": {}}
        remaining = []
        for item in data:
            if item.get("type") == "template":
                if "errors" in item and isinstance(item["errors"], dict):
                    templates["errors"].update(item["errors"])
                if "rate_limits" in item and isinstance(item["rate_limits"], dict):
                    templates["rate_limits"].update(item["rate_limits"])
            else:
                remaining.append(item)

        def _resolve_errors(obj: dict):
            """解析 errors 字段：若为模板引用则替换为实际值"""
            errs = obj.get("errors")
            if isinstance(errs, dict) and errs.get("type") == "template":
                tid = errs.get("id", "")
                if tid in templates["errors"]:
                    obj["errors"] = templates["errors"][tid]

        def _resolve_rate_limits(obj: dict):
            """解析 rate_limits 字段：将内联模板引用展开为实际规则"""
            rls = obj.get("rate_limits")
            if not isinstance(rls, list):
                return
            new_rls = []
            for rl in rls:
                if isinstance(rl, dict) and rl.get("type") == "template":
                    tid = rl.get("id", "")
                    if tid in templates["rate_limits"]:
                        new_rls.extend(templates["rate_limits"][tid])
                else:
                    new_rls.append(rl)
            obj["rate_limits"] = new_rls

        def _resolve_obj(obj: dict):
            if not isinstance(obj, dict):
                return
            _resolve_errors(obj)
            _resolve_rate_limits(obj)
            models = obj.get("models")
            if isinstance(models, dict):
                for mo in models.values():
                    if isinstance(mo, dict):
                        _resolve_errors(mo)
                        _resolve_rate_limits(mo)

        data.clear()
        for item in remaining:
            _resolve_obj(item)
            for key in item.get("keys", []):
                _resolve_obj(key)
            k = item.get("key")
            if isinstance(k, dict):
                _resolve_obj(k)
            data.append(item)

    def load(self):
        if not os.path.exists(POOLS_FILE):
            return
        try:
            with open(POOLS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._resolve_templates(data)
            for item in data:
                entry_type = item.get("type", "pool")
                if entry_type == "single":
                    entry = SingleAI.from_dict(item)
                    self.pools[entry.name] = entry
                else:
                    pool = AIPool.from_dict(item)
                    self.pools[pool.name] = pool
                    self.routers[pool.name] = PoolRouter(pool)
        except Exception as e:
            _logger.error("加载失败: %s", e)
        self._notify_change()


pool_manager = PoolManager()