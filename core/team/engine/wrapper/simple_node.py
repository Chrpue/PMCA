from __future__ import annotations
from typing import Sequence

from autogen_agentchat.agents import BaseChatAgent
from autogen_agentchat.base import Response, TaskResult
from autogen_agentchat.messages import BaseChatMessage, TextMessage
from autogen_core import CancellationToken
from loguru import logger

from base.runtime.task_context import PMCATaskContext
from core.team.common.team_messages import PMCARoutingMessages
from core.team.engine.complex_executor import PMCAComplexTaskTeam
from core.team.factory import PMCATeamFactory


class PMCASimpleTaskExecutorWrapper(BaseChatAgent):
    """将任意团队组件包装成 ChatAgent，以便 GraphFlow 调用."""

    def __init__(self, ctx: PMCATaskContext, name: str = "", description: str = ""):
        super().__init__(name=name, description=description)
        self._ctx = ctx
        # 初始状态：还未给团队分配任务
        self._is_first_call: bool = True

    @property
    def produced_message_types(self):
        return [TextMessage]

    async def on_messages(
        self,
        messages: Sequence[BaseChatMessage],
        cancellation_token: CancellationToken,
    ) -> Response:
        """收到新消息时调用团队运行，并返回团队的最终回复."""

        logger.info(f"节点 '{self.name}' 已激活，开始动态执行复杂任务...")

        triage_result = await self._ctx.task_workbench.get_item("triage_result")
        if triage_result.get("task_type") != "simple":
            raise ValueError(
                f"任务类型不匹配，simple 分支的 task_type 必须为 simple，当前类型为 {triage_result.get('task_type')}"
            )

        assistant_name = triage_result.get("assistant")

        assistant = self._ctx.assistant_factory.create_assistant(assistant_name)

        task_result: TaskResult = await assistant.run_stream(
            task=self._ctx.task_mission
        )

        final_message = task_result.messages[-1] if task_result.messages else None
        response_content = (
            f"简单任务执行完毕。停止原因: {task_result.stop_reason}\n\n"
            f"最终结果: {final_message.content if final_message else '无'}"  # type: ignore
        )

        return Response(
            chat_message=TextMessage(source=self.name, content=response_content),
            inner_messages=task_result.messages,
        )

    async def on_reset(self, cancellation_token: CancellationToken) -> None:
        """重置包装器和内部团队的状态。"""
        pass
