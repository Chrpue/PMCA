from __future__ import annotations
import re
from typing import Sequence, List, Type, AsyncGenerator, Union, Optional, Any

import json
from loguru import logger

from autogen_agentchat.agents import BaseChatAgent
from autogen_agentchat.base import Response, TaskResult
from autogen_agentchat.messages import BaseChatMessage, TextMessage, BaseAgentEvent
from autogen_core import CancellationToken

from base.runtime import PMCATaskContext


def _to_jsonable(obj: Any) -> Any:
    """将任意对象安全转换为 JSON 友好类型（支持 Pydantic v2 BaseModel）。"""
    if hasattr(obj, "model_dump") and callable(getattr(obj, "model_dump")):
        try:
            # pydantic v2：直接导出 dict；必要时可 mode='json'
            return obj.model_dump()  # 或 obj.model_dump(mode="json")
        except Exception:
            try:
                # 兼容 v1
                return obj.dict()  # type: ignore[attr-defined]
            except Exception:
                return str(obj)

    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    if isinstance(obj, dict):
        return {str(k): _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(v) for v in obj]

    return str(obj)


def _extract_json_block(text: str) -> Optional[str]:
    """从文本中提取 JSON（支持 ```json ... ``` 或裸 { ... }）。"""
    t = text.strip()
    if "```json" in t:
        try:
            return t.split("```json", 1)[1].split("```", 1)[0].strip()
        except IndexError:
            return None
    if t.startswith("{") and t.endswith("}"):
        return t
    return None


def _last_text_from_messages(
    msgs: Optional[Sequence[Union[BaseAgentEvent, BaseChatMessage]]],
) -> Optional[str]:
    """从末尾向前找最后一条 TextMessage 文本；跳过事件。"""
    if not msgs:
        return None
    for m in reversed(msgs):
        if isinstance(m, TextMessage) and m.content:
            return m.content
    return None


def _sanitize_source(s: str) -> str:
    """
    只保留字母、数字、下划线和连字符；其余替换为 '_'
    （可选）限制长度，避免模型或后端对 name/source 的长度约束
    """
    s = re.sub(r"[^A-Za-z0-9_-]", "_", s)
    return s[:64]


def _make_context_prefix(transcript: object, name: str) -> Optional[TextMessage]:
    """把 triage_transcript 打包成一条简短上下文提示，不逐字展开。"""
    try:
        compact = json.dumps(_to_jsonable(transcript), ensure_ascii=False)
        return TextMessage(
            source=_sanitize_source(f"{name}_context"),
            content="【分诊过程摘要，仅作为结构化总结的参考上下文；不要逐字复述】\n"
            + compact,
        )
    except Exception as e:
        logger.warning(f"[{name}] serialize triage_transcript failed: {e}")
        return None


class PMCATriageStructuredWrapper(BaseChatAgent):
    """
    结构化输出包装器：
    - 先从 workbench 读取 triage_transcript，注入为一条 context TextMessage
    - 调用被包裹 agent（流式/非流式均可）；中途事件透传
    - 末尾解析 JSON，写回 workbench['triage_result']；返回仅包含结构化文本的 Response
    - 不打印/拼装长历史
    """

    def __init__(self, name: str, ctx: PMCATaskContext, wrapped_agent: BaseChatAgent):
        super().__init__(name=name, description=wrapped_agent.description)
        self._ctx = ctx
        self._wrapped_agent = wrapped_agent

    @property
    def produced_message_types(self) -> List[Type[BaseChatMessage]]:
        return [TextMessage]

    async def on_reset(
        self, cancellation_token: CancellationToken | None = None
    ) -> None:
        await self._wrapped_agent.on_reset(cancellation_token)  # type: ignore

    async def on_messages_stream(
        self,
        messages: Sequence[BaseChatMessage],
        cancellation_token: CancellationToken,
    ) -> AsyncGenerator[Union[BaseAgentEvent, BaseChatMessage, Response], None]:
        # 1) 从 workbench 拉取分诊摘要作为上下文
        transcript = await self._ctx.task_workbench.get_item("triage_transcript")
        upstream: list[BaseChatMessage] = []
        ctx_msg = _make_context_prefix(transcript, self.name) if transcript else None
        if ctx_msg:
            upstream.append(ctx_msg)
        upstream.extend(messages)

        # 2) 调用被包裹 agent 的流式接口（run_stream -> 最后一项是 TaskResult）
        stream = self._wrapped_agent.on_messages_stream(upstream, cancellation_token)

        final_text: Optional[str] = None

        async for item in stream:
            if isinstance(item, Response):
                final_text = item.chat_message.content if item.chat_message else None  # type: ignore
                await self._parse_and_store_summary_text(final_text)
                yield Response(
                    chat_message=TextMessage(source=self.name, content=final_text or "")
                )

            elif isinstance(item, TaskResult):
                # 也兼容直接给 TaskResult 的团队
                txt = _last_text_from_messages(item.messages)
                final_text = txt or final_text
                await self._parse_and_store_summary_text(final_text)
                yield Response(
                    chat_message=TextMessage(source=self.name, content=final_text or "")
                )

            else:
                yield item

    # --------- 非流式（少量场景确需一次性结果） ---------
    async def on_messages(
        self,
        messages: Sequence[BaseChatMessage],
        cancellation_token: CancellationToken,
    ) -> Response:
        transcript = await self._ctx.task_workbench.get_item("triage_transcript")
        upstream: list[BaseChatMessage] = []
        ctx_msg = _make_context_prefix(transcript, self.name) if transcript else None
        if ctx_msg:
            upstream.append(ctx_msg)
        upstream.extend(messages)

        summary_response = await self._wrapped_agent.on_messages(
            upstream, cancellation_token
        )
        if not summary_response or not summary_response.chat_message:
            return Response(
                chat_message=TextMessage(
                    source=self.name,
                    content="[Error]: PMCATriageStructured 没有生成准确的结构化信息.",
                )
            )

        final_text = summary_response.chat_message.content  # type: ignore
        await self._parse_and_store_summary_text(final_text)
        return Response(
            chat_message=TextMessage(source=self.name, content=final_text or "")
        )

    # --------- 解析并保存 JSON ---------
    async def _parse_and_store_summary_text(self, text: Optional[str]) -> None:
        """
        从 LLM 输出中提取 JSON，成功则写回 workbench['triage_result']。
        """
        if not text:
            return
        json_str = _extract_json_block(text)
        if not json_str:
            # 允许 LLM 直接输出自然语言或延迟到后续节点；此处不强制报错
            return
        try:
            structured = json.loads(json_str)
            # 二次 JSON 化试探，确保完全可序列化（处理潜在 Pydantic 字段）
            _ = json.dumps(_to_jsonable(structured), ensure_ascii=False)
            await self._ctx.task_workbench.set_item("triage_result", structured)
            logger.debug(f"[{self.name}] stored triage_result")
        except json.JSONDecodeError as e:
            logger.error(f"[{self.name}] parse JSON failed: {e}; raw={json_str}")
        except Exception as e:
            logger.error(f"[{self.name}] store triage_result failed: {e}")

