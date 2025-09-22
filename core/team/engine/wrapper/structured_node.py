from __future__ import annotations
from typing import Sequence, List, Type

import json
from loguru import logger

from autogen_agentchat.agents import BaseChatAgent
from autogen_agentchat.base import Response
from autogen_agentchat.messages import BaseChatMessage, TextMessage
from autogen_core import CancellationToken

from base.runtime import PMCATaskContext


class PMCATriageStructuredWrapper(BaseChatAgent):
    """
    一个专用的封装器，它包裹了一个核心Agent来执行分诊结构化输出与工作台存储，
    """

    def __init__(self, name: str, ctx: PMCATaskContext, wrapped_agent: BaseChatAgent):
        """
        Args:
            name (str): 封装器的名称，这个名字将用于GraphFlow的节点。
            ctx (PMCATaskContext): 任务上下文，用于访问workbench。
            wrapped_agent (BaseChatAgent): 被包裹的核心Agent。
        """
        super().__init__(name=name, description=wrapped_agent.description)
        self._ctx = ctx
        self._wrapped_agent = wrapped_agent

    @property
    def produced_message_types(self) -> List[Type[BaseChatMessage]]:
        """【必需】此封装器最终产生的是TextMessage"""
        return [TextMessage]

    async def on_reset(
        self, cancellation_token: CancellationToken | None = None
    ) -> None:
        """【必需】重置时，需要同时重置被包裹的Agent"""
        await self._wrapped_agent.on_reset(cancellation_token)  # type: ignore

    async def on_messages(
        self,
        messages: Sequence[BaseChatMessage],
        cancellation_token: CancellationToken,
    ) -> Response:
        """
        执行“生成-处理-存储”的完整流程
        """

        summary_response = await self._wrapped_agent.on_messages(
            messages, cancellation_token
        )

        if not summary_response or not summary_response.chat_message:
            logger.warning(f"装饰器 '{self.name}' 没有接收到一个有效的输出.")
            return Response(
                chat_message=TextMessage(
                    source=self.name,
                    content="[Error]: PMCATriageStructured 没有生成准确的结构化信息.",
                )
            )

        summary_message = summary_response.chat_message

        await self._parse_and_store_summary(summary_message)

        final_response_message = TextMessage(
            source=self.name,
            content=summary_message.content,  # type: ignore
        )

        return Response(
            chat_message=final_response_message,
            inner_messages=getattr(summary_message, "inner_messages", None),
        )

    async def _parse_and_store_summary(self, msg: BaseChatMessage):
        """
        负责解析和异步存储的核心逻辑。
        """
        if not isinstance(msg, TextMessage) or not msg.content:
            logger.warning(
                f"装饰器 '{self.name}' 未能从 PMCATriageStructured 接收到有效信息."
            )
            return

        json_str = self._extract_json(msg.content)

        if json_str:
            try:
                structured_data = json.loads(json_str)
                await self._ctx.task_workbench.set_item(
                    "triage_result", structured_data
                )
                logger.success(
                    f"'{self.name}' successfully stored triage summary to workbench."
                )
            except json.JSONDecodeError as e:
                logger.error(
                    f"'{self.name}' failed to parse JSON: {e}. Original text: '{json_str}'"
                )
        else:
            logger.warning(
                f"'{self.name}' could not find a JSON block in the message content."
            )

    def _extract_json(self, text: str) -> str | None:
        """从文本中稳健地提取JSON字符串。"""
        if "```json" in text:
            try:
                return text.split("```json", 1)[1].split("```", 1)[0].strip()
            except IndexError:
                return None
        elif text.strip().startswith("{") and text.strip().endswith("}"):
            return text.strip()
        return None
