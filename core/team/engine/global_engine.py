import json
from loguru import logger
from typing import List

from autogen_agentchat.teams import DiGraphBuilder, GraphFlow
from autogen_agentchat.conditions import MaxMessageTermination
from autogen_agentchat.messages import BaseChatMessage

from base.runtime import PMCATaskContext
from core.team.common import PMCATriageResult
from .complex_task_proxy import ComplexTaskProxyAgent
from .triage_proxy import TriageProxyAgent


class PMCAMainGraphEngine:
    """
    构建并管理顶层的 GraphFlow，实现持续对话的循环服务。
    这个版本将所有团队构建逻辑都封装在各自的代理节点中。
    """

    def __init__(self, ctx: PMCATaskContext):
        self._ctx = ctx
        self.builder = DiGraphBuilder()
        self._build_nodes()
        self._build_edges()

    async def _get_last_triage_result(
        self, messages: List[BaseChatMessage]
    ) -> PMCATriageResult | None:
        """从对话历史中提取最后一个由 TriageProxyAgent 发出的 TriageResult。"""
        for msg in reversed(messages):
            if msg.source == "TriageProxyAgent":
                try:
                    triage_result = PMCATriageResult.model_validate_json(msg.content)
                    await self._ctx.task_workbench.set_item(
                        "triage_result", triage_result
                    )
                    logger.debug(f"已将分诊结果存入工作台: {msg.content}")
                    return triage_result
                except Exception as e:
                    logger.error(f"解析 TriageProxyAgent 的输出失败: {e}")
        return None

    async def _is_simple_task(self, messages: List[BaseChatMessage]) -> bool:
        result = await self._get_last_triage_result(messages)
        return result is not None and result.task_type == "simple_task"

    async def _is_complex_task(self, messages: List[BaseChatMessage]) -> bool:
        result = await self._get_last_triage_result(messages)
        return result is not None and result.task_type == "complex_task"

    def _build_nodes(self):
        """定义 GraphFlow 中的所有节点，现在它们都是独立的 Agent 或 AgentProxy。"""
        factory = self._ctx.assistant_factory

        # 节点1: 分诊代理节点
        triage_proxy = TriageProxyAgent(
            ctx=self._ctx,
            name="TriageProxyAgent",
            description="负责接待用户初始任务，并在内部分类任务的代理。",
            system_message="我负责对任务进行分诊。",
        )
        self.builder.add_node(triage_proxy)

        # 节点2: 简单任务处理器
        simple_solver = factory.create_assistant("PMCASimpleSolver")
        self.builder.add_node(simple_solver)

        # 节点3: 复杂任务代理节点
        complex_task_proxy = ComplexTaskProxyAgent(
            ctx=self._ctx,
            name="PMCAComplexTaskProxy",
            description="一个代理智能体，负责启动和管理专家团队来完成复杂任务。",
            system_message="我是一个复杂任务的代理。",
        )
        self.builder.add_node(complex_task_proxy)

    def _build_edges(self):
        """定义节点之间的连接关系和循环。"""
        # 【重要】我们将 UserProxy 作为图的“枢纽”来简化循环
        # 注意：这里我们假设 UserProxy 节点由 factory 创建，并且它能处理来自不同节点的输入
        user_proxy = self._ctx.assistant_factory.create_assistant("PMCAUserProxy")
        self.builder.add_node(user_proxy)

        # 1. 流程从 UserProxy 开始，将任务交给分诊代理
        self.builder.add_edge("PMCAUserProxy", "TriageProxyAgent")

        # 2. 从分诊代理出来后，根据条件分支
        self.builder.add_edge(
            "TriageProxyAgent", "PMCASimpleSolver", condition=self._is_simple_task
        )
        self.builder.add_edge(
            "TriageProxyAgent", "PMCAComplexTaskProxy", condition=self._is_complex_task
        )

        # 3. 两个分支执行完毕后，都将最终结果返回给用户代理，形成对话闭环
        self.builder.add_edge(
            "PMCASimpleSolver", "PMCAUserProxy", condition="[TASK_COMPLETE]"
        )
        self.builder.add_edge(
            "PMCAComplexTaskProxy", "PMCAUserProxy", condition="[TASK_COMPLETE]"
        )

        # 4. 设置入口点
        self.builder.set_entry_point("PMCAUserProxy")

    def build(self) -> GraphFlow:
        """构建并返回最终的 GraphFlow 实例。"""
        return GraphFlow(
            participants=self.builder.get_participants(),
            graph=self.builder.build(),
            termination_condition=MaxMessageTermination(max_messages=30),
        )
