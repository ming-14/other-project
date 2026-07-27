"""消息发送器

处理用户聊天消息的发送、流式接收和显示。

输出格式（路由模式）：
    [via Provider / model...]              ← 路由时立即显示
    [via Provider / model...] 重试中...       ← 失败时追加重试信息
    [model_name thinking]                  ← 思考模型
    [model_name]                           ← 回复模型
        回复内容...
  ---- in N, out N, ctk xx% | via label ----

输出格式（直连模式）：
    [model_name thinking]                  ← 思考模型
    [model_name]                           ← 回复模型
        回复内容...
  ---- in N, out N, ctk xx% | via label ----

ctk = prompt_tokens / context_length × 100%（模型未配置 context_length 时默认 128000）
"""

from __future__ import annotations

from core.pool import pool_manager
from core.client import stream_chat
from core.i18n import t
from cli.printer.format import error, system


def _short_model_name(model_id: str) -> str:
    """提取简短的模型名用于显示

    例如:
        deepseek/deepseek-r1  -> deepseek-r1
        openrouter/owl-alpha  -> owl-alpha
        GLM-4.5-Flash        -> GLM-4.5-Flash
    """
    return model_id.split("/")[-1] if "/" in model_id else model_id


class _StreamPrinter:
    """流式缩进打印机

    逐 chunk 接收文本，保持 4 空格缩进，正确处理跨 chunk 的换行。
    """

    def __init__(self, indent: str = "    "):
        self.indent = indent
        self._at_line_start = True

    def write(self, text: str):
        """写入文本块，自动缩进

        Args:
            text: 文本块（可能跨多行）
        """
        parts = text.split("\n")
        for i, part in enumerate(parts):
            if i > 0:
                print()  # 裸换行（缩进由下一行的 at_line_start 处理）
                self._at_line_start = True
            if not part:
                # 空段：由前导换行产生（如 "\nHello" → ["", "Hello"]），
                # 仅触发换行即可，不打印多余缩进
                continue
            if self._at_line_start:
                print(self.indent, end="", flush=True)
                self._at_line_start = False
            print(part, end="", flush=True)


class Sender:
    """消息发送混入类"""

    def _send_message(self, text: str):
        """发送聊天消息

        Args:
            text: 用户输入的文本
        """
        if not self.current_entry_name:
            error(t("sender.error.not_connected"))
            return
        if self.streaming:
            error(t("sender.error.streaming"))
            return

        # 添加用户消息
        self.messages.append({"role": "user", "content": text})

        entry = pool_manager.get_entry(self.current_entry_name)
        if not entry:
            error(t("sender.error.entry_not_exists", name=self.current_entry_name))
            return

        # 构建参数字典
        params_dict = self.params.to_dict() if hasattr(self.params, "to_dict") else {}
        messages = list(self.messages)
        if self.params.system_prompt:
            full_messages = [{"role": "system", "content": self.params.system_prompt}]
            full_messages.extend(messages)
        else:
            full_messages = messages

        self.streaming = True
        self.stop_flag = False

        # 判断调用来源：池路由 / 池直连 / 普通 AI
        if self.mode == "pool":
            router = pool_manager.get_router(self.current_entry_name)
            if not router:
                error(t("sender.error.no_router"))
                self.streaming = False
                return

            if self.selected_pool_key is not None:
                # 池直连模式：固定使用指定的 key
                pool = pool_manager.get_pool(self.current_entry_name)
                if not pool or self.selected_pool_key >= len(pool.keys):
                    error(t("sender.error.invalid_key_index", idx=self.selected_pool_key))
                    self.streaming = False
                    return
                kc = pool.keys[self.selected_pool_key]
                mo = kc.models.get(self.selected_model)
                ctx_len = mo.context_length if mo else None
                self._stream_send(
                    kc.base_url, kc.api_key, self.selected_model,
                    full_messages, params_dict, kc.errors.timeout or 60, kc.type,
                    label=f"{kc.label or kc.base_url} / {self.selected_model}",
                    context_length=ctx_len,
                )
            else:
                # 池路由模式
                self._stream_route(router, full_messages, params_dict)
        else:
            # 普通 AI 模式
            entry_single = pool_manager.get_single(self.current_entry_name)
            if not entry_single:
                error(t("sender.error.not_single_ai", name=self.current_entry_name))
                self.streaming = False
                return
            kc = entry_single.key
            mo = kc.models.get(self.selected_model)
            ctx_len = mo.context_length if mo else None
            self._stream_send(
                kc.base_url, kc.api_key, self.selected_model,
                full_messages, params_dict, kc.errors.timeout or 60, kc.type,
                label=f"{kc.label or kc.base_url} / {self.selected_model}",
                context_length=ctx_len,
            )

        self.streaming = False

    # ------------------------------------------------------------------
    # 流式发送（单次）
    # ------------------------------------------------------------------

    def _stream_send(
        self, base_url: str, api_key: str, model: str,
        messages: list[dict], params: dict, timeout: int, api_type: str,
        label: str = "", context_length: int | None = None,
    ):
        """执行单次流式请求，边收边显示

        Args:
            base_url: API 基础地址
            api_key:  API Key
            model:    模型 ID
            messages: 完整消息列表
            params:   参数字典
            timeout:  超时秒数
            api_type: API 格式类型
            label:    完成时显示的后缀标签
        """
        short_name = _short_model_name(model)
        reasoning_parts: list[str] = []
        content_lines: list[str] = []
        usage_data: dict | None = None
        phase = "thinking"  # "thinking" | "content"
        printer = _StreamPrinter()
        had_content = False

        def on_reasoning(text: str):
            """推理内容回调：流式显示 thinking 区块"""
            nonlocal phase
            if phase != "thinking":
                return
            if not reasoning_parts:
                print(f"[{short_name} thinking]")
            print(text, end="", flush=True)
            reasoning_parts.append(text)

        def on_usage(usage: dict):
            nonlocal usage_data
            usage_data = usage

        try:
            for chunk in stream_chat(
                base_url=base_url, api_key=api_key, model=model,
                messages=messages, params=params,
                stop_check=lambda: self.stop_flag,
                timeout=timeout, api_type=api_type,
                on_reasoning=on_reasoning,
                on_usage=on_usage,
            ):
                # 首次收到内容时切换到 content 阶段
                if phase == "thinking":
                    if reasoning_parts:
                        print()  # thinking 结束换行
                    print(f"[{short_name}]")
                    phase = "content"
                # 流式输出缩进内容
                printer.write(chunk)
                content_lines.append(chunk)
                had_content = True

            # 流结束后的尾巴
            if not had_content and not reasoning_parts:
                # 完全无内容
                return

            # token 用量 + 完成行（合并为页脚格式）
            if usage_data:
                ctx_len = context_length or 128000
                ctk_val = usage_data['prompt_tokens'] / ctx_len * 100
                print(f"\n  ---- in {usage_data['prompt_tokens']}, "
                      f"out {usage_data['completion_tokens']}, "
                      f"ctk {ctk_val:.0f}% | via {label} ----")
            else:
                print(f"\n  ---- | via {label} ----")

            full_text = "".join(content_lines)
            self.messages.append({"role": "assistant", "content": full_text})

        except Exception as e:
            print()
            error(t("sender.error.request_failed", e=e))

    # ------------------------------------------------------------------
    # 流式发送（池路由 + 故障转移）
    # ------------------------------------------------------------------

    def _stream_route(self, router, messages: list[dict], params: dict):
        """池路由模式：自动重试 + 故障转移，边收边显示

        输出格式：
            [via Provider / model...]          ← 路由时立即显示
            [via Provider / model...] 重试中...   ← 失败时追加重试信息
            [model_name thinking]              ← 思考模型
            [model_name]                       ← 回复模型 / 思考结束转回复
                回复内容...
              ---- in N, out N, ctk xx% | via label ----

        Args:
            router:   PoolRouter 实例
            messages: 完整消息列表
            params:   参数字典
        """
        try:
            while True:
                selected = router.select_entry()
                if selected is None:
                    error(t("sender.error.all_disabled"))
                    break
                ki, mid, kc, mo = selected
                short_name = _short_model_name(mid)
                reasoning_parts: list[str] = []
                content_lines: list[str] = []
                usage_data: dict | None = None
                phase = "thinking"
                printer = _StreamPrinter()
                had_content = False
                label = f"{kc.label or kc.base_url} / {mid}"

                # 立即显示路由信息（不换行，等待结果）
                print(f"[via {label}...]", end="", flush=True)

                def on_reasoning(text: str):
                    nonlocal phase
                    if phase != "thinking":
                        return
                    if not reasoning_parts:
                        # 首个推理块：换行结束 [via...] 行，打印 thinking 头
                        print(f"\n[{short_name} thinking]")
                    print(text, end="", flush=True)
                    reasoning_parts.append(text)

                def on_usage(usage: dict):
                    nonlocal usage_data
                    usage_data = usage

                try:
                    for chunk in stream_chat(
                        base_url=kc.base_url, api_key=kc.api_key, model=mid,
                        messages=messages, params=params,
                        stop_check=lambda: self.stop_flag,
                        timeout=kc.errors.timeout or 60, api_type=kc.type,
                        on_reasoning=on_reasoning,
                        on_usage=on_usage,
                    ):
                        if phase == "thinking":
                            if reasoning_parts:
                                # thinking 块已有单独行，换行后打 content 头
                                print()
                            else:
                                # 无 thinking：先换行结束 [via...] 行
                                print()
                            print(f"[{short_name}]")
                            phase = "content"
                        printer.write(chunk)
                        content_lines.append(chunk)
                        had_content = True

                    # 成功
                    router.report_success(ki, mid)
                    if had_content or reasoning_parts:
                        # 页脚：统计 + via 信息（合并为一行）
                        if usage_data:
                            ctx_len = mo.context_length or 128000
                            ctk_val = usage_data['prompt_tokens'] / ctx_len * 100
                            print(f"\n  ---- in {usage_data['prompt_tokens']}, "
                                  f"out {usage_data['completion_tokens']}, "
                                  f"ctk {ctk_val:.0f}% | via {label} ----")
                        else:
                            print(f"\n  ---- | via {label} ----")
                        self.messages.append({
                            "role": "assistant",
                            "content": "".join(content_lines),
                        })
                    break

                except Exception as e:
                    router.report_error(ki, mid, kc)
                    err_msg = str(e)
                    # 在 [via...] 行追加失败信息
                    print(f" {t('sender.info.retrying', err=err_msg[:60])}")
                    continue
        except Exception as e:
            print()
            error(t("sender.error.route_failed", e=e))