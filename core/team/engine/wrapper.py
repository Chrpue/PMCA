from __future__ import annotations
from typing import Sequence

from autogen_agentchat.agents import BaseChatAgent
from autogen_agentchat.base import Response
from autogen_agentchat.messages import BaseChatMessage, TextMessage
from autogen_core import CancellationToken
from loguru import logger

from core.team.engine.team_base import PMCATeamBase


class PMCATeamWrapper(BaseChatAgent):
    """将任意团队组件包装成 ChatAgent，以便 GraphFlow 调用."""

    def __init__(self, team: PMCATeamBase, name: str = "", description: str = ""):
        super().__init__(name=name, description=description)
        self._team = team
        # 初始状态：还未给团队分配任务
        self._is_first_call: bool = True
        self._final_response = None

    @property
    def produced_message_types(self):
        # 团队输出的是助手文本消息
        return [TextMessage]

    async def on_messages(
        self,
        messages: Sequence[BaseChatMessage],
        cancellation_token: CancellationToken,
    ) -> Response:
        """收到新消息时调用团队运行，并返回团队的最终回复."""
        await self._team.initialize_team()

        # 第一次调用时，将用户消息作为任务文本；后续调用直接继续历史对话
        task = None
        if self._is_first_call:
            # 找到最后一条用户消息作为任务文本
            for msg in reversed(messages):
                # logger.success(msg)
                if isinstance(msg, TextMessage) and msg.source == "PMCAUserProxy":  # type: ignore
                    task = msg.content
                    break
            self._is_first_call = False

        # 使用团队运行，并根据 ctx 配置自动选择 console/service 模式
        chat_output = await self._team.run_chat(
            task=task,
            mode=self._team.ctx.task_env.INTERACTION_MODE,
            custom_callable=None,
        )
        # 从 TaskResult 中取出最后一条助手消息作为代理的回复
        final_msg: TextMessage = chat_output.messages[-1]  # type: ignore
        self._final_response = Response(chat_message=final_msg)

        return self._final_response

    async def on_reset(self, cancellation_token: CancellationToken) -> None:
        """重置包装器和内部团队的状态。"""
        await self._team.reset()
