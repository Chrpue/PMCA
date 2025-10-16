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


class PMCASwarmWrapper(BaseChatAgent):
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

        logger.success("已进入")

        self._final_response = Response(
            chat_message=TextMessage(source=self.name, content="its ok"),
            # inner_messages=triage_conversation_history,
        )

        return self._final_response

    async def on_reset(self, cancellation_token: CancellationToken) -> None:
        """重置包装器和内部团队的状态。"""
        await self._team.reset()
