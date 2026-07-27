"""AI 池/模型切换与管理命令

提供 /model、/models、/status、/pool-create、/delete、/rename、
/fetchmodels、/test、/edit 等命令的实现。
"""

from __future__ import annotations

from core.pool import pool_manager
from core.models import AIPool, SingleAI, ModelOverride, LimitRule, ErrorConfig as ErrCfg
from core.i18n import t
from cli.printer.format import error, success, info, header, divider, dim, system
from cli.printer.pool_display import print_pools, print_pool_detail
from cli.printer.route_status import print_route_status
from core.pool import test_pool


class PoolCommands:
    """池/模型切换与管理命令混入类"""

    def do_model(self, arg: str):
        """
        /model <id|name>              按别名/名称切换条目
        /model <id>:<model>           切换条目并指定模型
        /model <池>:<key>:<model>     直连池内指定 Key
        """
        from cli.printer.format import warning
        arg = arg.strip()

        subcmd_match = arg.split(None, 1)
        if subcmd_match and subcmd_match[0] in ("delete", "rename", "edit", "test"):
            subcmd, subarg = subcmd_match[0], subcmd_match[1] if len(subcmd_match) > 1 else ""
            pool_sub_map = {
                "delete": self._pool_delete,
                "rename": self._pool_rename,
                "edit": self._pool_edit,
                "test": self._pool_test,
            }
            pool_sub_map[subcmd](subarg)
            return

        if not arg:
            error(t("model.error.usage"))
            return

        parts = arg.split(":")
        if len(parts) == 3:
            pool_name, key_str, model_id = parts
            entry = pool_manager.get_entry(pool_name)
            if not entry or not isinstance(entry, AIPool):
                error(t("model.error.pool_not_found", pool_name=pool_name))
                return
            try:
                key_idx = int(key_str)
            except ValueError:
                error(t("model.error.key_index_not_number"))
                return
            if key_idx < 0 or key_idx >= len(entry.keys):
                error(t("model.error.key_index_out_of_range", n=len(entry.keys) - 1))
                return
            kc = entry.keys[key_idx]
            if model_id not in kc.models:
                error(t("model.error.model_not_in_key", model_id=model_id, label=kc.label))
                return
            self.mode = "pool"
            self.current_entry_name = pool_name
            self.selected_model = model_id
            self.selected_pool_key = key_idx
            router = pool_manager.get_router_for_session(pool_name)
            if router:
                router.set_active_groups(None)
            success(t("model.success.direct_connect", pool_name=pool_name, key_str=key_str, model_id=model_id))
            self._update_prompt()
            return

        if len(parts) == 2:
            entry_name, model_id = parts
            result = pool_manager.resolve_model(entry_name)
            if not result:
                error(t("model.error.entry_not_found", entry_name=entry_name))
                return
            real_name, _, is_pool = result
            entry = pool_manager.get_entry(real_name)
            if not entry:
                error(t("model.error.entry_not_exists", real_name=real_name))
                return
            if isinstance(entry, AIPool):
                for ki, kc in enumerate(entry.keys):
                    if model_id in kc.models:
                        self.mode = "pool"
                        self.current_entry_name = real_name
                        self.selected_model = model_id
                        self.selected_pool_key = ki
                        router = pool_manager.get_router_for_session(real_name)
                        if router:
                            router.set_active_groups(None)
                        success(t("model.success.direct_connect", pool_name=real_name, key_str=ki, model_id=model_id))
                        self._update_prompt()
                        return
                error(t("model.error.model_not_in_any_key", model_id=model_id, real_name=real_name))
            else:
                if model_id not in entry.models:
                    error(t("model.error.model_not_in_entry", model_id=model_id, real_name=real_name))
                    return
                self.mode = "single"
                self.current_entry_name = real_name
                self.selected_model = model_id
                self.selected_pool_key = None
                success(t("model.success.switch_with_model", real_name=real_name, model_id=model_id))
                self._update_prompt()
            return

        query = arg.strip()
        result = pool_manager.resolve_model(query)
        if not result:
            error(t("model.error.not_found", query=query))
            return
        entry_name, first_model, is_pool = result
        entry = pool_manager.get_entry(entry_name)
        if not entry:
            error(t("model.error.entry_not_exists", real_name=entry_name))
            return
        if is_pool:
            self.mode = "pool"
            self.selected_pool_key = None
            self.selected_model = ""
            router = pool_manager.get_router_for_session(entry_name)
            if router:
                router.set_active_groups(None)
            success(t("model.success.switch_route", entry_name=entry_name))
        else:
            self.mode = "single"
            self.selected_pool_key = None
            self.selected_model = first_model
            success(t("model.success.switch_model", entry_name=entry_name, first_model=first_model))
        self.current_entry_name = entry_name
        self._update_prompt()

    def do_models(self, arg: str):
        """列出所有配置条目 / 拉取远程模型列表

        子命令:
            fetch   拉取当前 single AI 的远程模型列表
        """
        if arg.strip().lower() == "fetch":
            return self._fetch_models("")
        entries = pool_manager.get_all_entries_info()
        if not entries:
            info(t("models.info.no_config"))
            return
        header(t("models.header.all_config"))
        for i, e in enumerate(entries, 1):
            if e["is_pool"]:
                tag = t("models.tag.pool")
                status = t("models.status.enabled") if e["enabled"] else t("models.status.disabled")
                print(f"  {i}. [{tag}] {e['name']} [{status}] "
                      f"(Key: {e['key_count']}, {t('models.tag.pool')}: {e['model_count']})")
            else:
                tag = t("models.tag.single")
                alias = f" ({t('models.label.alias')}: {e['alias']})" if e.get("alias") else ""
                status = t("models.status.enabled") if e["enabled"] else t("models.status.disabled")
                label = f" [{e['label']}]" if e.get("label") else ""
                print(f"  {i}. [{tag}] {e['name']}{alias}{label} [{status}] "
                      f"({t('models.tag.model_count')}: {e['model_count']})")
        print()

    def _fetch_models(self, arg: str):
        """拉取当前 single AI 的远程模型列表"""
        from cli.printer.format import warning
        if not self.current_entry_name or self.mode != "single":
            error(t("fetch.error.not_single_mode"))
            return
        entry = pool_manager.get_single(self.current_entry_name)
        if not entry:
            error(t("fetch.error.not_single_ai", name=self.current_entry_name))
            return
        from core.client import fetch_models
        try:
            success(t("fetch.info.fetching"))
            model_ids, details = fetch_models(
                entry.key.base_url, entry.key.api_key, entry.key.type
            )
            if not model_ids:
                warning(t("fetch.warning.no_models"))
                return
            entry.models = {mid: ModelOverride(model_id=mid) for mid in model_ids}
            success(t("fetch.success.fetched", n=len(model_ids)))
            for mid in model_ids[:10]:
                print(f"  - {mid}")
            if len(model_ids) > 10:
                print(t("fetch.info.more_models", n=len(model_ids) - 10))
        except Exception as e:
            error(t("fetch.error.failed", e=e))

    def do_status(self, arg: str):
        """查看当前状态"""
        header(t("status.header.current"))
        mode_map = {"pool": t("status.mode.pool_route"), "single": t("status.mode.single")}
        mode_label = mode_map.get(self.mode, t("status.mode.disconnected"))
        print(f"  {t('status.field.mode')}:       {mode_label}")
        print(f"  {t('status.field.entry')}:   {self.current_entry_name or t('status.value.none')}")
        print(f"  {t('status.field.model')}:   {self.selected_model or t('status.value.none')}")
        if self.selected_pool_key is not None:
            print(f"  {t('status.field.direct_key')}:   {self.selected_pool_key}")
        print(f"  {t('status.field.msg_count')}:     {len(self.messages)}")
        print(f"  {t('status.field.streaming')}:   {t('status.value.yes') if self.streaming else t('status.value.no')}")
        print()

        if self.mode == "pool" and self.current_entry_name:
            router = pool_manager.get_router(self.current_entry_name)
            if router:
                active_groups = router.get_active_groups()
                if active_groups is not None:
                    dim(f"  {t('status.field.mode')}: {', '.join(sorted(active_groups))}")
                else:
                    dim(f"  {t('status.info.all_groups_active')}")
                print()
                print_route_status(router)

    def _pool_create(self, arg: str):
        """新建 AI 池: /pool create <name>"""
        name = arg.strip()
        if not name:
            error(t("pool.error.usage_create"))
            return
        if pool_manager.get_entry(name):
            error(t("pool.error.entry_exists", name=name))
            return
        pool = AIPool(name=name)
        pool_manager.add_entry(pool)
        success(t("pool.success.created", name=name))

    def _pool_delete(self, arg: str):
        """删除配置: /pool delete <name>"""
        name = arg.strip()
        if not name:
            error(t("pool.error.usage_delete"))
            return
        if not pool_manager.get_entry(name):
            error(t("pool.error.entry_not_exists", name=name))
            return
        pool_manager.remove_entry(name)
        if self.current_entry_name == name:
            self.mode = ""
            self.current_entry_name = ""
            self.selected_model = ""
            self.selected_pool_key = None
        success(t("pool.success.deleted", name=name))

    def _pool_rename(self, arg: str):
        """重命名: /pool rename <old> <new>"""
        parts = arg.split()
        if len(parts) < 2:
            error(t("pool.error.usage_rename"))
            return
        old_name, new_name = parts[0], parts[1]
        if not pool_manager.get_entry(old_name):
            error(t("pool.error.entry_not_exists", name=old_name))
            return
        if pool_manager.get_entry(new_name):
            error(t("pool.error.entry_exists", name=new_name))
            return
        if pool_manager.rename_entry(old_name, new_name):
            if self.current_entry_name == old_name:
                self.current_entry_name = new_name
            success(t("pool.success.renamed", old_name=old_name, new_name=new_name))
        else:
            error(t("pool.error.rename_failed"))

    def _pool_test(self, arg: str):
        """测试池/普通 AI: /pool test [name]"""
        name = arg.strip() or self.current_entry_name
        if not name:
            error(t("pool.error.usage_test"))
            return

        pool = pool_manager.get_pool(name)
        if pool:
            success(t("pool.test.start_pool", name=name))
            key_details = []
            for kc in pool.keys:
                for mid in kc.models:
                    key_details.append((kc, mid))
            if not key_details:
                error(t("pool.test.no_models"))
                return
            for idx, (kc, mid) in enumerate(key_details):
                label = kc.label or kc.base_url
                print(f"  [{idx + 1}/{len(key_details)}] {label} / {mid} ...")
                ok, msg = test_pool(pool.name, kc, mid)
                if ok:
                    success(f"    OK: {msg}")
                else:
                    error(f"    FAIL: {msg}")
            return

        single = pool_manager.get_single(name)
        if single:
            models = list(single.models)
            if not models:
                error(t("pool.test.no_models_single", name=name))
                return
            import time
            success(t("pool.test.start_single", name=name, n=len(models)))
            for idx, mid in enumerate(models):
                print(f"  [{idx + 1}/{len(models)}] {mid} ...")
                ok, msg = test_pool(single.name, single.key, mid)
                if ok:
                    success(f"    OK: {msg}")
                else:
                    error(f"    FAIL: {msg}")
                if idx < len(models) - 1:
                    dim(f"    {t('pool.test.wait_next')}")
                    time.sleep(5)
            return

        error(t("pool.error.entry_not_exists", name=name))

    def _pool_edit(self, arg: str):
        """编辑配置: /pool edit <name> 或 /model edit <name>"""
        name = arg.strip()
        if not name:
            error(t("pool.error.usage_edit"))
            return
        entry = pool_manager.get_entry(name)
        if not entry:
            error(t("pool.error.entry_not_exists", name=name))
            return
        if isinstance(entry, AIPool):
            from cli.pool_editor.editor import PoolEditor
            editor = PoolEditor(entry, name)
        else:
            from cli.pool_editor.single_editor import SingleEditor
            editor = SingleEditor(entry, name)
        editor.run()
        pool_manager.update_entry(entry)
        success(t("pool.success.updated", name=name))

    # ------------------------------------------------------------------
    # /pool 子命令：create / delete / rename / edit / test
    # ------------------------------------------------------------------

    def do_pool(self, arg: str):
        """/pool 子命令入口

        子命令:
            create <name>    新建 AI 池
            delete <name>    删除配置
            rename <a> <b>   重命名
            edit <name>      编辑
            test [name]      一键测试
        """
        parts = arg.strip().split(None, 1)
        if not parts:
            error(t("pool.error.usage"))
            return
        subcmd = parts[0].lower()
        subarg = parts[1] if len(parts) > 1 else ""

        sub_map = {
            "create": self._pool_create,
            "delete": self._pool_delete,
            "rename": self._pool_rename,
            "edit": self._pool_edit,
            "test": self._pool_test,
        }
        handler = sub_map.get(subcmd)
        if handler:
            handler(subarg)
        else:
            error(t("pool.error.unknown_subcmd", subcmd=subcmd))
