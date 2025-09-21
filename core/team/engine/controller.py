from typing import Optional
from autogen_agentchat.agents import (
    AssistantAgent,
    BaseChatAgent,
    MessageFilterAgent,
    MessageFilterConfig,
    PerSourceFilter,
)
from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
from autogen_agentchat.teams import DiGraphBuilder, GraphFlow

from base.runtime.task_context import PMCATaskContext
from core.team.common.team_messages import PMCARoutingMessages
from core.team.core_assistants.user_proxy import PMCAUserProxy

from .triage import PMCATriageTeam
from .wrapper import PMCATeamWrapper


class PMCAFlowController:
    def __init__(self, ctx: PMCATaskContext) -> None:
        self._ctx = ctx
        # 流程构建器
        self._builder = DiGraphBuilder()
        # 核心组件成员
        self._user_proxy: Optional[PMCAUserProxy] = None
        self._task_triage_group: Optional[BaseChatAgent] = None
        self._task_simple_group = None
        self._task_complex_group = None

        self._initialize: bool = False
        self._overall_graph: Optional[GraphFlow] = None

    @property
    def overall_graph(self):
        if not self._initialize:
            self.initialize()
        return self._overall_graph

    def _build_user_proxy(self) -> PMCAUserProxy:
        """
        构建用户代理
        """
        return PMCAUserProxy(self._ctx)

    def _build_triage_team(self) -> None:
        """
        构建分诊团队
        """
        if not self._task_triage_group:
            self._task_triage_group = PMCATeamWrapper(
                PMCATriageTeam(self._ctx), "GraphTriageWrapper"
            )

    def initialize(self):
        self._user_proxy = self._build_user_proxy()
        self._build_triage_team()
        self._build_overall_graph()
        self._initialize = True

    def _build_overall_graph(self):
        if self._task_triage_group is None or self._user_proxy is None:
            raise ValueError(
                "无法构建 GraphFlow，因为必需的组件（triage_group 或 user_proxy）尚未初始化。"
            )

        wrapped_triage = MessageFilterAgent(
            name="GraphTriageFilter",
            wrapped_agent=self._task_triage_group,
            filter=MessageFilterConfig(
                per_source=[
                    PerSourceFilter(source="PMCAUserProxy", position="last", count=1)
                ]
            ),
        )

        summarizer_core = self._ctx.assistant_factory.create_assistant(
            "PMCATriageStructured"
        )

        self._builder.add_node(self._user_proxy)
        self._builder.add_node(wrapped_triage)
        self._builder.add_node(summarizer_core)

        self._builder.add_edge(
            self._user_proxy,
            wrapped_triage,
            # activation_group="task_triage",
        )

        self._builder.add_edge(
            wrapped_triage,
            self._user_proxy,
            # activation_group="task_retriage",
            # condition=lambda msg: PMCARoutingMessages.ROUNDROBIN_FAILURE.value
            # in msg.to_model_text(),
            condition=lambda msg: False,
        )

        self._builder.add_edge(
            wrapped_triage,
            summarizer_core,
            # activation_group="task_finish",
            # condition=lambda msg: PMCARoutingMessages.ROUNDROBIN_SUCCESS.value
            # in msg.to_model_text(),
            condition=lambda msg: True,
        )

        self._builder.set_entry_point(self._user_proxy)
        graph = self._builder.build()
        termination_condition = (
            MaxMessageTermination(20)
            | TextMentionTermination(PMCARoutingMessages.TASK_FAILURE)
            | TextMentionTermination(PMCARoutingMessages.TASK_SUCCESS)
        )

        self._overall_graph = GraphFlow(
            participants=self._builder.get_participants(),
            graph=graph,
            termination_condition=termination_condition,
        )
