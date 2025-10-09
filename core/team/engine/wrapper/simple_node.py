from __future__ import annotations
from typing import Sequence
from loguru import logger

from autogen_agentchat.agents import BaseChatAgent
from autogen_agentchat.base import Response, TaskResult
from autogen_agentchat.messages import BaseChatMessage, TextMessage
from autogen_core import CancellationToken

from base.runtime.task_context import PMCATaskContext
from core.team.common.team_messages import PMCARoutingMessages
from core.team.engine.simple_executor import PMCASimpleTaskTeam
from core.team.factory import PMCATeamFactory


class PMCASimpleTaskExecutorWrapper(BaseChatAgent):
    """将任意团队组件包装成 ChatAgent，以便 GraphFlow 调用."""

    def __init__(
        self,
        ctx: PMCATaskContext,
        name: str = "",
        description: str = "",
    ):
        super().__init__(name=name, description=description)
        self._ctx = ctx
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

        logger.info(f"节点 '{self.name}' 已激活，开始动态执行简单任务...")

        # 1. 【运行时创建团队】
        #    此时，triage_result 肯定已经存在于 workbench 中了。
        #    我们在这里安全地调用异步工厂来创建团队。
        try:
            # 使用 .create() 动态构建一个功能齐全的团队实例
            simple_team_instance = await PMCASimpleTaskTeam.create(
                self._ctx, "DynamicSimpleTeam", "动态创建的简单任务执行团队"
            )
        except Exception as e:
            # 如果因为 triage_result 问题导致创建失败，在这里捕获并报告
            error_msg = f"在运行时创建简单任务团队失败: {e}"
            logger.exception(error_msg)
            return Response(
                chat_message=TextMessage(source=self.name, content=error_msg)
            )

        # 2. 【运行动态创建的团队】
        #    从上下文中获取初始任务，交给这个新团队去执行
        task = self._ctx.task_mission

        task_result: TaskResult = await simple_team_instance.discuss(
            task=task,
            mode=self._ctx.task_env.INTERACTION_MODE,
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
        # await self._team.reset()
