from __future__ import annotations

import shlex

from core.models import ModelOverride
from core.i18n import t
from ..printer.format import error, success, warning
from .helpers import parse_idx, get_key


class ModelCommands:
    def do_models(self, arg):
        """列出所有 Key 下的模型及其状态"""
        parts = shlex.split(arg) if arg else []
        if parts:
            idx = parse_idx(parts[0])
        else:
            idx = None
        for ki, kc in enumerate(self.pool.keys):
            if idx is not None and ki != idx:
                continue
            label = kc.label or kc.base_url
            status = t("model_cmd.status.enabled") if kc.enabled else t("model_cmd.status.disabled")
            print(f"[{ki}] {label} [{status}]")
            for mid, mo in kc.models.items():
                mstatus = t("model_cmd.status.enabled") if mo.enabled else t("model_cmd.status.disabled")
                print(f"    - {mid} [{mstatus}]")
            print()

    def do_model_add(self, arg):
        parts = shlex.split(arg)
        if len(parts) < 2:
            error(t("model_cmd.error.usage_add"))
            return
        idx = parse_idx(parts[0])
        if idx is None:
            return
        kc = get_key(self.pool.keys, idx)
        if kc is None:
            return
        model_id = parts[1]
        if model_id in kc.models:
            warning(t("model_cmd.warning.exists", model_id=model_id))
            return
        kc.models[model_id] = ModelOverride(model_id=model_id)
        self._mark_modified()
        success(t("model_cmd.success.added", model_id=model_id, label=kc.label or kc.base_url))

    def do_model_remove(self, arg):
        parts = shlex.split(arg)
        if len(parts) < 2:
            error(t("model_cmd.error.usage_remove"))
            return
        idx = parse_idx(parts[0])
        if idx is None:
            return
        kc = get_key(self.pool.keys, idx)
        if kc is None:
            return
        model_id = parts[1]
        if model_id not in kc.models:
            error(t("model_cmd.error.not_found", model_id=model_id))
            return
        del kc.models[model_id]
        self._mark_modified()
        success(t("model_cmd.success.removed", model_id=model_id))

    def do_model_enable(self, arg):
        """启用模型: model-enable <key索引> <model_id>"""
        parts = shlex.split(arg)
        if len(parts) < 2:
            error(t("model_cmd.error.usage_enable"))
            return
        idx = parse_idx(parts[0])
        if idx is None:
            return
        kc = get_key(self.pool.keys, idx)
        if kc is None:
            return
        model_id = parts[1]
        if model_id not in kc.models:
            error(t("model_cmd.error.not_found", model_id=model_id))
            return
        kc.models[model_id].enabled = True
        self._mark_modified()
        success(t("model_cmd.success.enabled", model_id=model_id))

    def do_model_disable(self, arg):
        """禁用模型: model-disable <key索引> <model_id>"""
        parts = shlex.split(arg)
        if len(parts) < 2:
            error(t("model_cmd.error.usage_disable"))
            return
        idx = parse_idx(parts[0])
        if idx is None:
            return
        kc = get_key(self.pool.keys, idx)
        if kc is None:
            return
        model_id = parts[1]
        if model_id not in kc.models:
            error(t("model_cmd.error.not_found", model_id=model_id))
            return
        kc.models[model_id].enabled = False
        self._mark_modified()
        success(t("model_cmd.success.disabled", model_id=model_id))

    def do_model_param(self, arg):
        parts = shlex.split(arg)
        if len(parts) < 4:
            error(t("model_cmd.error.usage_param"))
            error(t("model_cmd.info.param_fields"))
            return
        idx = parse_idx(parts[0])
        if idx is None:
            return
        kc = get_key(self.pool.keys, idx)
        if kc is None:
            return
        model_id, field, value_str = parts[1], parts[2], parts[3]
        if model_id not in kc.models:
            error(t("model_cmd.error.not_found", model_id=model_id))
            return
        try:
            value = int(value_str)
        except ValueError:
            error(t("model_cmd.error.value_not_int"))
            return
        mo = kc.models[model_id]
        field_map = {
            "concurrency": "max_concurrency",
            "timeout": "timeout",
            "max-errors": "max_errors",
            "max-requests": "max_requests",
            "failure-pause": "failure_pause",
            "context-length": "context_length",
        }
        py_field = field_map.get(field)
        if not py_field:
            error(t("model_cmd.error.unknown_field", field=field))
            return
        setattr(mo, py_field, value)
        self._mark_modified()
        success(t("model_cmd.success.param_set", model_id=model_id, field=field, value=value))
