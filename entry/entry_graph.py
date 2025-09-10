from autogen_agentchat.conditions import (
    ExternalTermination,
    MaxMessageTermination,
    TextMentionTermination,
)
from loguru import logger
from typing import List, Dict, Any
from autogen_agentchat.agents import (
    MessageFilterAgent,
    MessageFilterConfig,
    PerSourceFilter,
)
from autogen_agentchat.teams import DiGraphBuilder, GraphFlow
from autogen_agentchat.ui import Console
from autogen_agentchat.messages import StructuredMessage
from autogen_core.tools import StaticWorkbench, ToolResult, ToolSchema

from base.runtime.system_workbench import PMCATaskContext
from core.team.factory import PMCATeamFeedBack
from core.assistant.special_agents import PMCADecision, PMCAUser
from core.assistant.special_agents import DecisionResponse
from entry.team_boostrap_proxy import TeamBootstrapProxy
from entry.decision_reviewer_proxy import DecisionReviewerProxy


# class APPWorkbench(StaticWorkbench):
#     """Light-Weight key-value workbench with no additional tools."""
#
#     def __init__(self) -> None:
#         super().__init__(tools=[])
#         self._kv: dict[str, Any] = {}
#
#     async def set_item(self, key: str, value: Any) -> None:
#         self._kv[key] = value
#
#     async def get_item(self, key: str) -> Any:
#         return self._kv.get(key)
#
#     async def list_tools(self) -> List[ToolSchema]:
#         return []
#
#     async def call_tool(
#         self,
#         name: str,
#         arguments: Dict[str, Any],
#         call_id: str | None = None,
#         caller=None,
#         message=None,
#         **kwargs,
#     ) -> ToolResult:
#         raise RuntimeError("在Workbench中没有可用的工具")


class PMCAEntryGraph:
    """构建ENTRY工作流"""

    @staticmethod
    def graph_termination():
        return (
            ExternalTermination()
            | MaxMessageTermination(max_messages=80)
            | TextMentionTermination(
                PMCATeamFeedBack.GRAPHFINISHED, sources="PMCAGraphFinished"
            )
        )

    @staticmethod
    def team_finished(msg):
        return PMCATeamFeedBack.FINISHED in msg.content

    @staticmethod
    def need_user_input(msg):
        return PMCATeamFeedBack.NEEDUSER in msg.content

    @staticmethod
    def need_decision(msg, wb) -> bool:
        return (
            PMCATeamFeedBack.QUIT not in msg.content.upper()
            and "team_state" not in wb._kv
        )

    @staticmethod
    def team_resume(msg, wb) -> bool:
        state = (
            msg.source.startswith("PMCAUserProxy")
            and "team_state" in wb._kv
            and wb._kv.get("team_state") is not None
        )
        return state

    @staticmethod
    def activate_finished(msg, wb):
        return (
            PMCATeamFeedBack.QUIT in msg.content.upper()
            and "team_state" in wb._kv
            and wb._kv.get("team_state") is not None
        )

    @staticmethod
    def reactive_finished(msg, wb) -> bool:
        return (
            PMCATeamFeedBack.FINISHED in msg.content.upper()
            and "team_state" in wb._kv
            and wb._kv.get("team_state") is not None
        )

    @staticmethod
    async def begin(task_ctx: PMCATaskContext):
        """Entry"""

        await PMCADecision.obtain_agents_duties(task_ctx)
        (
            team_decision,
            team_decision_critic,
        ) = await PMCADecision.obtain_team_decision_components(task_ctx)

        (
            agents_decision,
            agents_decision_critic,
        ) = await PMCADecision.obtain_agents_decision_components(task_ctx)

        decision_reviewer = await PMCADecision.obtain_decision_reviewer_components(
            task_ctx
        )

        finished = task_ctx.agent_factory.create_agent("PMCAGraphFinished")
        user_proxy = PMCAUser().agent

        # 包装批评代理，确保按照指定消息流触发
        filter_team_decision_critic = MessageFilterAgent(
            name="PMCATeamDecisionCritic",
            wrapped_agent=team_decision_critic,
            filter=MessageFilterConfig(
                per_source=[
                    PerSourceFilter(source="PMCAUserProxy", position=None, count=1),
                    PerSourceFilter(
                        source="PMCATeamDecision", position="last", count=1
                    ),
                ]
            ),
        )
        filter_agents_decision_critic = MessageFilterAgent(
            name="PMCAAgentsDecisionCritic",
            wrapped_agent=agents_decision_critic,
            filter=MessageFilterConfig(
                per_source=[
                    PerSourceFilter(source="PMCAUserProxy", position=None, count=1),
                    PerSourceFilter(
                        source="PMCAAgentsDecision", position="last", count=1
                    ),
                ]
            ),
        )
        # 包装决策代理，按顺序产出决策结果
        filter_agents_decision = MessageFilterAgent(
            name="PMCAAgentsDecision",
            wrapped_agent=agents_decision,
            filter=MessageFilterConfig(
                per_source=[
                    PerSourceFilter(source="PMCAUserProxy", position="first", count=1),
                    PerSourceFilter(
                        source="PMCAAgentsDecisionCritic", position="last", count=1
                    ),
                ]
            ),
        )
        filter_team_decision = MessageFilterAgent(
            name="PMCATeamDecision",
            wrapped_agent=team_decision,
            filter=MessageFilterConfig(
                per_source=[
                    PerSourceFilter(source="PMCAUserProxy", position="first", count=1),
                    PerSourceFilter(
                        source="PMCATeamDecisionCritic", position="last", count=1
                    ),
                ]
            ),
        )

        proxy_decision_reviewer = DecisionReviewerProxy(decision_reviewer, task_ctx)
        team_bootstrap_proxy = TeamBootstrapProxy("PMCATeamBoostrapProxy", task_ctx)

        builder = DiGraphBuilder()
        builder.add_node(user_proxy, activation="any")
        builder.add_node(filter_team_decision, activation="any")
        builder.add_node(filter_team_decision_critic, activation="all")
        builder.add_node(filter_agents_decision, activation="any")
        builder.add_node(filter_agents_decision_critic, activation="all")
        builder.add_node(proxy_decision_reviewer, activation="all")
        builder.add_node(team_bootstrap_proxy, activation="any")
        builder.add_node(finished, activation="all")

        # 定义节点之间的消息传递条件和流转
        builder.add_edge(
            user_proxy,
            filter_team_decision,
            activation_group="team_decision_start",
            condition=lambda m, _wb=cfg.app_workbench: PMCAEntryGraph.need_decision(
                m, _wb
            ),
        )
        builder.add_edge(
            user_proxy,
            filter_agents_decision,
            activation_group="agents_decision_start",
            condition=lambda m, _wb=cfg.app_workbench: PMCAEntryGraph.need_decision(
                m, _wb
            ),
        )
        builder.add_edge(
            filter_team_decision,
            filter_team_decision_critic,
            activation_group="critic_team_decision",
        )
        builder.add_edge(
            filter_agents_decision,
            filter_agents_decision_critic,
            activation_group="critic_agents_decision",
        )
        builder.add_edge(
            filter_team_decision_critic,
            proxy_decision_reviewer,
            activation_group="team_decision_done",
            condition=lambda m: PMCATeamFeedBack.TEAMDECISIONCOMPLETE in m.content,  # type: ignore
        )
        builder.add_edge(
            filter_team_decision_critic,
            filter_team_decision,
            activation_group="revise_team_decision",
            condition=lambda m: PMCATeamFeedBack.TEAMDECISIONREVISE in m.content,  # type: ignore
        )
        builder.add_edge(
            filter_agents_decision_critic,
            proxy_decision_reviewer,
            activation_group="agents_decision_done",
            condition=lambda m: PMCATeamFeedBack.AGENTSDECISIONCOMPLETE in m.content,  # type: ignore
        )
        builder.add_edge(
            filter_agents_decision_critic,
            filter_agents_decision,
            activation_group="revise_agents_decision",
            condition=lambda m: PMCATeamFeedBack.AGENTSDECISIONREVISE in m.content,  # type: ignore
        )
        builder.add_edge(
            proxy_decision_reviewer,
            team_bootstrap_proxy,
            activation_group="team_start",
            condition=lambda m: PMCATeamFeedBack.OVERALLDECISIONCOMPLETE in m.content,  # type: ignore
        )
        builder.add_edge(
            team_bootstrap_proxy,
            user_proxy,
            activation_group="team_finished",
            condition=PMCAEntryGraph.team_finished,
        )
        builder.add_edge(
            team_bootstrap_proxy,
            user_proxy,
            activation_group="need_user_input",
            condition=PMCAEntryGraph.need_user_input,
        )
        builder.add_edge(
            user_proxy,
            team_bootstrap_proxy,
            activation_group="team_resume",
            condition=lambda m, _wb=cfg.app_workbench: PMCAEntryGraph.team_resume(
                m, _wb
            ),
        )
        builder.add_edge(
            user_proxy,
            finished,
            activation_group="active_finished",
            condition=lambda m, _wb=cfg.app_workbench: PMCAEntryGraph.activate_finished(
                m, _wb
            ),
        )

        builder.add_edge(
            team_bootstrap_proxy,
            finished,
            activation_group="reactive_finished",
            condition=lambda m, _wb=cfg.app_workbench: PMCAEntryGraph.reactive_finished(
                m, _wb
            ),
        )

        builder.set_entry_point(user_proxy)
        graph = builder.build()
        workflow = GraphFlow(
            builder.get_participants(),
            graph=graph,
            custom_message_types=[StructuredMessage[DecisionResponse]],
            termination_condition=PMCAEntryGraph.graph_termination(),
        )
        await Console(workflow.run_stream())
