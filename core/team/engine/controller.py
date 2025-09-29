import json
import re
from typing import Optional, Any, Dict
from autogen_agentchat.agents import (
    AssistantAgent,
    BaseChatAgent,
    MessageFilterAgent,
    MessageFilterConfig,
    PerSourceFilter,
)
from autogen_agentchat.conditions import (
    MaxMessageTermination,
    SourceMatchTermination,
    TextMentionTermination,
)
from autogen_agentchat.messages import BaseChatMessage, TextMessage
from autogen_agentchat.teams import DiGraphBuilder, GraphFlow
from loguru import logger

from base.runtime.task_context import PMCATaskContext
from core.team.common.team_messages import PMCARoutingMessages
from core.team.core_assistants.user_proxy import PMCAUserProxy
from core.team.engine.wrapper import (
    PMCATriageTeamWrapper,
    PMCATriageStructuredWrapper,
    PMCAComplexTaskExecutorWrapper,
    PMCASimpleTaskExecutorWrapper,
)
from core.team.core_assistants import PMCACoreAssistants

from .triage import PMCATriageTeam


class PMCAFlowController:
    def __init__(self, ctx: PMCATaskContext) -> None:
        self._ctx = ctx
        # 流程构建器
        self._builder = DiGraphBuilder()
        # 核心组件成员
        self._user_proxy: Optional[PMCAUserProxy] = None
        self._task_triage_group: Optional[BaseChatAgent] = None
        self._task_triage_structured: Optional[BaseChatAgent] = None
        self._task_simple_node: Optional[BaseChatAgent] = None
        self._task_complex_group: Optional[BaseChatAgent] = None

        self._initialize: bool = False
        self._overall_graph: Optional[GraphFlow] = None

    @property
    async def overall_graph(self):
        if not self._initialize or self._overall_graph is None:
            await self.initialize()
        return self._overall_graph

    def _build_user_proxy(self) -> PMCAUserProxy:
        """
        构建用户代理
        """
        return PMCAUserProxy(self._ctx)

    async def _build_triage_structured(self) -> None:
        """
        构建分诊结果结构化输出节点
        """
        if not self._task_triage_structured:
            self._task_triage_structured = PMCATriageStructuredWrapper(
                name="PMCATriageStructuredWrapper",
                ctx=self._ctx,
                wrapped_agent=self._ctx.assistant_factory.create_assistant(
                    PMCACoreAssistants.TRIAGE_STRUCTURED.value
                ),
            )

    async def _build_triage_team(self) -> None:
        """
        构建分诊团队
        """
        if not self._task_triage_group:
            team = await PMCATriageTeam.create(self._ctx, "PMCATriageTeam", "分诊团队")
            self._task_triage_group = PMCATriageTeamWrapper(
                self._ctx,
                team,
                "PMCATriageTeamWrapper",
            )

    def _build_complex_team(self) -> None:
        """
        构建复杂任务团队
        """
        if not self._task_complex_group:
            self._task_complex_group = PMCAComplexTaskExecutorWrapper(
                self._ctx,
                "PMCAComplexTaskTeamWrapper",
                "一个负责动态执行复杂任务的节点",
            )

    def _build_simple_node(self) -> None:
        """
        构建简单任务节点
        """
        if not self._task_simple_node:
            self._task_simple_node = PMCASimpleTaskExecutorWrapper(
                self._ctx,
                "PMCASimpleTaskTeamWrapper",
                "一个负责动态执行简单任务的节点",
            )

    async def initialize(self):
        self._user_proxy = self._build_user_proxy()
        await self._build_triage_team()
        await self._build_triage_structured()
        self._build_complex_team()
        self._build_simple_node()
        await self._build_overall_graph()
        self._initialize = True

    async def _build_overall_graph(self):
        if (
            self._task_triage_group is None
            or self._user_proxy is None
            or self._task_triage_structured is None
            or self._task_complex_group is None
            or self._task_simple_node is None
        ):
            raise ValueError(
                "无法构建 GraphFlow，因为必需的组件（triage_group 或 user_proxy）尚未初始化。"
            )

        self._builder.add_node(self._user_proxy)
        self._builder.add_node(self._task_triage_group)
        self._builder.add_node(self._task_triage_structured)
        self._builder.add_node(self._task_complex_group)
        self._builder.add_node(self._task_simple_node)

        self._builder.add_edge(
            self._user_proxy,
            self._task_triage_group,
            activation_condition="any",
            # activation_group="task_triage",
        )

        self._builder.add_edge(
            self._task_triage_group,
            self._user_proxy,
            condition=lambda m: PMCAFlowController.condition_edge_triage_failure(m),
        )

        self._builder.add_edge(
            self._task_triage_group,
            self._task_triage_structured,
            condition=lambda m: PMCAFlowController.condition_edge_triage_success(m),
        )

        # 添加复杂任务的边
        self._builder.add_edge(
            self._task_triage_structured,
            self._task_complex_group,
            condition=lambda m: PMCAFlowController.condition_edge_task_type(
                m, "complex"
            ),
        )

        # 添加简单任务的边
        self._builder.add_edge(
            self._task_triage_structured,
            self._task_simple_node,
            condition=lambda m: PMCAFlowController.condition_edge_task_type(
                m, "simple"
            ),
        )

        self._builder.set_entry_point(self._user_proxy)
        graph = self._builder.build()

        termination_condition = MaxMessageTermination(20)

        self._overall_graph = GraphFlow(
            participants=self._builder.get_participants(),
            graph=graph,
            termination_condition=termination_condition,
        )

    @staticmethod
    def condition_edge_triage_failure(msg):
        return PMCARoutingMessages.TRIAGE_FAILURE.value in msg.content

    @staticmethod
    def condition_edge_triage_success(msg):
        return PMCARoutingMessages.TRIAGE_SUCCESS.value in msg.content

    @staticmethod
    def condition_edge_task_type(msg, expected_type: str) -> bool:
        data = PMCAFlowController._get_json_from_message(msg)
        if data and isinstance(data, dict):
            task_type = data.get("task_type")
            if isinstance(task_type, str) and task_type.strip() == expected_type:
                return True
        return False

    # @staticmethod
    # def condition_edge_complex(msg):
    #     logger.error(msg.content)
    #     return '"task_type": "complex"' in msg.content

    @staticmethod
    def _get_json_from_message(msg: Any) -> Optional[Dict]:
        """
        一个健壮的辅助方法，用于从消息内容中提取并解析JSON。
        """
        if not hasattr(msg, "content") or not isinstance(msg.content, str):
            return None

        # 使用正则表达式来寻找被包裹的JSON块
        match = re.search(r"\{.*\}", msg.content, re.DOTALL)
        if not match:
            return None

        try:
            # 尝试解析找到的JSON字符串
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            # 如果解析失败，返回None
            return None
