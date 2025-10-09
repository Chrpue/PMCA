from __future__ import annotations
from typing import Sequence
from loguru import logger

from autogen_agentchat.agents import BaseChatAgent
from autogen_agentchat.base import Response, TaskResult
from autogen_agentchat.messages import BaseChatMessage, TextMessage
from autogen_core import CancellationToken

from base.runtime.task_context import PMCATaskContext
from core.team.common.team_messages import PMCARoutingMessages
from core.team.factory import PMCATeamFactory


class PMCATriageTeamWrapper(BaseChatAgent):
    """将任意团队组件包装成 ChatAgent，以便 GraphFlow 调用."""

    def __init__(
        self,
        ctx: PMCATaskContext,
        team: PMCATeamFactory,
        name: str = "",
        description: str = "",
    ):
        super().__init__(name=name, description=description)
        self._ctx = ctx
        self._team = team
        # 初始状态：还未给团队分配任务
        self._is_first_call: bool = True
        self._final_response = None

    @property
    def produced_message_types(self):
        return [TextMessage]

    async def on_messages(
        self,
        messages: Sequence[BaseChatMessage],
        cancellation_token: CancellationToken,
    ) -> Response:
        """收到新消息时调用团队运行，并返回团队的最终回复."""

        # 第一次调用时，将用户消息作为任务文本；后续调用直接继续历史对话
        task = None
        if self._is_first_call:
            # 找到最后一条用户消息作为任务文本
            for msg in reversed(messages):
                if isinstance(msg, TextMessage) and msg.source == "PMCAUserProxy":  # type: ignore
                    task = msg.content
                    break
            self._is_first_call = False

        task = self._ctx.task_mission
        logger.error(task)

        # 使用团队运行，并根据 ctx 配置自动选择 console/service 模式
        task_result: TaskResult = await self._team.discuss(
            task=task,
            mode=self._team.ctx.task_env.INTERACTION_MODE,
            custom_callable=None,
        )

        triage_conversation_history = task_result.messages or []

        formatted_history = "对用户任务的分诊过程讨论内容：\n"
        for msg in triage_conversation_history:
            try:
                msg_dict = msg.model_dump()
                formatted_history += (
                    f"---- 发言人：{msg_dict.get('source', '未知')} ----\n"
                )
                formatted_history += f"{msg_dict.get('content', '')}\n\n"
            except Exception:
                formatted_history += (
                    f"---- 发言人：{getattr(msg, 'source', '未知')} ----\n"
                )
                formatted_history += f"{getattr(msg, 'content', '')}\n\n"

        stop_reason = task_result.stop_reason or ""
        final_content = formatted_history

        if PMCARoutingMessages.TRIAGE_SUCCESS.value in stop_reason:
            final_content += f"{PMCARoutingMessages.TRIAGE_SUCCESS.value}"

        self._final_response = Response(
            chat_message=TextMessage(source=self.name, content=final_content),
            # inner_messages=triage_conversation_history,
        )

        return self._final_response

    async def on_reset(self, cancellation_token: CancellationToken) -> None:
        """重置包装器和内部团队的状态。"""
        await self._team.reset()
