import json
import sys
from pathlib import Path


def fmt_ctx(val):
    if val is None:
        return "?"
    if val >= 1000:
        return f"{val // 1000}k"
    return str(val)


def fmt_time(secs: int) -> str:
    if secs < 180 or secs % 60 != 0:
        return f"{secs}s"
    total_min = secs // 60
    hours = total_min // 60
    mins = total_min % 60
    if hours and mins:
        return f"{hours}h{mins}m"
    elif hours:
        return f"{hours}h"
    else:
        return f"{mins}m"


def _resolve_templates(data: list[dict]) -> None:
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
        errs = obj.get("errors")
        if isinstance(errs, dict) and errs.get("type") == "template":
            tid = errs.get("id", "")
            if tid in templates["errors"]:
                obj["errors"] = templates["errors"][tid]

    def _resolve_rate_limits(obj: dict):
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


def _fmt_rl(rl, indent="       "):
    t = rl["type"]
    ts = fmt_time(rl["time"])
    if t == "time_per_req":
        return f"{indent}单次间隔>={ts}"
    elif t == "count_per_time":
        return f"{indent}每{ts}最多{rl['count']}次"
    elif t == "tokens_per_time":
        return f"{indent}每{ts}最多{rl['tokens']}token"
    return f"{indent}未知类型 {t}"


def _fmt_rl_list(rls, indent="       "):
    if not rls:
        return ""
    return "\n".join(_fmt_rl(rl, indent) for rl in rls)


_ERR_LABELS = {
    "max_concurrency":      ("并发", ""),
    "timeout":              ("超时", "s"),
    "max_errors":           ("错误上限", ""),
    "failure_pause":        ("失败暂停", "s"),
    "max_errors_model":     ("模型错误上限", ""),
    "failure_pause_model":  ("模型冷却", "s"),
}


def _fmt_errors(errs):
    if not errs:
        return ""
    parts = []
    for k, v in errs.items():
        if v is None:
            continue
        label, unit = _ERR_LABELS.get(k, (k, ""))
        parts.append(f"{label}={v}{unit}")
    return ", ".join(parts) if parts else ""


def _fmt_modalities(modalities):
    if not modalities:
        return ""
    inp = ",".join(modalities.get("input", []))
    outp = ",".join(modalities.get("output", []))
    return f"[{inp}→{outp}]"


def show_pools(path, show_apikey=False):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    _resolve_templates(data)

    def _mask(key):
        return key if show_apikey else "***"

    for entry in data:
        enabled_tag = "" if entry.get("enabled", True) else " [禁用]"
        if entry["type"] == "single":
            k = entry["key"]
            print(f"[Single] {k['label']}{enabled_tag}")
            print(f"  name     : {entry['name']}")
            print(f"  type     : {k['type']}")
            print(f"  base_url : {k['base_url']}")
            print(f"  api_key  : {_mask(k['api_key'])}")
            print(f"  models   : {', '.join(entry['models'])}")
            if entry.get("alias"):
                print(f"  alias    : {entry['alias']}")
            print()

        elif entry["type"] == "pool":
            print(f"[Pool] {entry['name']}{enabled_tag}")
            for key in entry["keys"]:
                key_tag = " [禁用]" if not key.get("enabled", True) else ""
                print(f"  ── {key['label']}{key_tag} ──")
                print(f"     type     : {key['type']}")
                print(f"     base_url : {key['base_url']}")
                print(f"     api_key  : {_mask(key['api_key'])}")
                groups = key.get("groups")
                if groups and groups != ["other"]:
                    print(f"     groups   : {', '.join(groups)}")
                err_str = _fmt_errors(key.get("errors"))
                if err_str:
                    print(f"     errors   : {err_str}")
                rl_str = _fmt_rl_list(key.get("rate_limits"))
                if rl_str:
                    print(f"     rate_limits:\n{rl_str}")
                mreq = key.get("max_requests")
                if mreq:
                    print(f"     max_requests : {mreq}")
                print(f"     models:")
                for mname, minfo in key.get("models", {}).items():
                    model_tag = " [禁用]" if not minfo.get("enabled", True) else ""
                    extra = ""
                    ctx = minfo.get("context-length")
                    if ctx:
                        extra += f"  ctx={fmt_ctx(ctx)}"
                    family = minfo.get("family")
                    if family:
                        extra += f"  [{family}]"
                    reasoning = minfo.get("reasoning")
                    if reasoning is not None:
                        extra += f"  reasoning={'Y' if reasoning else 'N'}"
                    tool_call = minfo.get("tool_call")
                    if tool_call is not None:
                        extra += f"  tool={'Y' if tool_call else 'N'}"
                    attachment = minfo.get("attachment")
                    if attachment is not None:
                        extra += f"  attach={'Y' if attachment else 'N'}"
                    modalities = minfo.get("modalities")
                    if modalities:
                        extra += f"  {_fmt_modalities(modalities)}"
                    knowledge = minfo.get("knowledge")
                    if knowledge:
                        extra += f"  know={knowledge}"
                    err_str = _fmt_errors(minfo.get("errors"))
                    if err_str:
                        extra += f"  errors({err_str})"
                    rl_str = _fmt_rl_list(minfo.get("rate_limits"), indent="              ")
                    if rl_str:
                        extra += f"  rate_limits"
                    mreq = minfo.get("max_requests")
                    if mreq:
                        extra += f"  max_req={mreq}"
                    print(f"       - {mname}{model_tag}{extra}")
                    if rl_str:
                        print(rl_str)
                print()
            print()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", default=r"pools.json")
    parser.add_argument("--show-apikey", action="store_true")
    args = parser.parse_args()

    import io
    buf = io.StringIO()
    out = sys.stdout
    sys.stdout = buf
    show_pools(args.path, show_apikey=args.show_apikey)
    sys.stdout = out
    out_path = Path(args.path).parent / "pools.txt"
    Path(out_path).write_text(buf.getvalue(), encoding="utf-8")
    print(f"Written to {out_path}")
