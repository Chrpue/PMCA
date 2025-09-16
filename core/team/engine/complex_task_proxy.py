from typing import List
from loguru import logger

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.base import Response
from autogen_agentchat.messages import BaseChatMessage, TextMessage

from base.runtime import PMCATaskContext
from core.team.common import PMCATriageResult
from .selector_group import PMCASelectorGroup


class ComplexTaskProxyAgent(AssistantAgent):
    """
    这是一个运行时代理，它不被注册在工厂中，也没有持久化记忆。
    它的唯一作用是在 GraphFlow 中充当一个节点，负责动态构建并执行
    一个 SelectorGroupChat 团队来处理复杂任务。
    """

    def __init__(self, ctx: PMCATaskContext, **kwargs):
        super().__init__(**kwargs)
        self._ctx = ctx

    async def on_messages(self, messages: List[BaseChatMessage]) -> Response:
        triage_result: PMCATriageResult = await self._ctx.task_workbench.get_item(
            "triage_result"
        )

        if not triage_result or not triage_result.required_executors:
            logger.error("ComplexTaskProxy 未能从工作台获取有效的执行团队列表。")
            return Response(
                chat_message=TextMessage(
                    source=self.name,
                    content="无法启动复杂任务，因为缺少执行团队信息。\n[TASK_COMPLETE]",
                )
            )

        participant_names = [
            "PMCAOrchestrator",
            "PMCAUserProxy",
        ] + triage_result.required_executors

        logger.info(
            f"--- 启动复杂任务执行系统 (选定团队: {triage_result.required_executors}) ---"
        )
        group_builder = PMCASelectorGroup(ctx=self._ctx)
        execution_team = group_builder.build()

        task = messages[-1].content
        result = await execution_team.run(task=task)

        final_answer = (
            result.messages[-1].content
            if result.messages
            else "复杂任务已执行，但未产生最终结果。"
        )

        return Response(
            chat_message=TextMessage(
                source=self.name, content=f"{final_answer}\n[TASK_COMPLETE]"
            )
        )
