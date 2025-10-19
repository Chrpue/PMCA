from __future__ import annotations
from typing import Sequence, AsyncGenerator, Union, Optional

from autogen_agentchat.agents import BaseChatAgent
from autogen_agentchat.base import Response, TaskResult
from autogen_agentchat.messages import BaseChatMessage, TextMessage, BaseAgentEvent
from autogen_core import CancellationToken
from loguru import logger

from base.runtime.task_context import PMCATaskContext
from core.team.common.team_messages import PMCARoutingMessages
from core.team.engine.complex_executor import PMCAComplexTaskTeam
from core.team.factory import PMCATeamFactory


class PMCAComplexTaskExecutorWrapper(BaseChatAgent):
    """将任意团队组件包装成 ChatAgent，以便 GraphFlow 调用."""

    def __init__(self, ctx: PMCATaskContext, name: str = "", description: str = ""):
        super().__init__(name=name, description=description)
        self._ctx = ctx
        # 初始状态：还未给团队分配任务
        self._is_first_call: bool = True

    @property
    def produced_message_types(self):
        return [TextMessage]

    async def on_messages_stream(
        self,
        messages: Sequence[BaseChatMessage],
        cancellation_token: CancellationToken,
    ) -> AsyncGenerator[Union[BaseAgentEvent, BaseChatMessage, Response], None]:
        logger.info(
            f"[{self.name}] complex-node stream start; new_messages={len(messages)}"
        )
        await self._ctx.ensure_runtime_started()

        complex_team = await PMCAComplexTaskTeam.create(
            self._ctx, "DynamicComplexTeam", "动态创建的复杂任务执行团队"
        )

        effective_task: Optional[Sequence[BaseChatMessage]] = messages or None

        stream = await complex_team.discuss(
            task=effective_task,
            output_task_messages=True,
        )

        async for item in stream:
            if isinstance(item, TaskResult):
                last = (
                    item.messages[-1]
                    if item.messages
                    else TextMessage(source=self.name, content="")
                )
                content = (
                    f"[COMPLEX_DONE] stop={item.stop_reason or ''}\n"
                    f"{last.content if isinstance(last, TextMessage) else ''}"
                )
                yield Response(
                    chat_message=TextMessage(source=self.name, content=content),
                    inner_messages=item.messages,
                )
            else:
                yield item

    async def on_messages(
        self,
        messages: Sequence[BaseChatMessage],
        cancellation_token: CancellationToken,
    ) -> Response:
        logger.info(
            f"[{self.name}] complex-node non-stream start; new_messages={len(messages)}"
        )

        await self._ctx.ensure_runtime_started()

        complex_team = await PMCAComplexTaskTeam.create(
            self._ctx, "DynamicComplexTeam", "动态创建的复杂任务执行团队"
        )

        effective_task: Optional[Sequence[BaseChatMessage]] = messages or None

        result: TaskResult = await complex_team.discuss(
            task=effective_task,
            output_task_messages=True,
        )

        last = (
            result.messages[-1]
            if result.messages
            else TextMessage(source=self.name, content="")
        )
        content = (
            f"[COMPLEX_DONE] stop={result.stop_reason or ''}\n"
            f"{last.content if isinstance(last, TextMessage) else ''}"
        )
        return Response(
            chat_message=TextMessage(source=self.name, content=content),
            inner_messages=result.messages,
        )

    async def on_reset(self, cancellation_token: CancellationToken) -> None:
        """重置包装器和内部团队的状态。"""
        self._is_first_call = True
