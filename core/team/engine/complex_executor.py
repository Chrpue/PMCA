from typing import List
from autogen_agentchat.base import ChatAgent, Team
from autogen_agentchat.teams import RoundRobinGroupChat, SelectorGroupChat
from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
from base.prompts.complex_task.complex_task_prompt import (
    PMCACOMPLEXTASK_SELECTORGROUP_SYSTEM_MESSAGE,
)
from base.runtime.task_context import PMCATaskContext
from core.team.common.team_messages import PMCARoutingMessages
from core.team.core_assistants import PMCACoreAssistants
from core.team.factory import PMCATeamFactory

from .swarm import PMCASwarm


class PMCAComplexTaskTeam(PMCATeamFactory):
    def __init__(
        self, ctx: PMCATaskContext, name: str, description: str, *, use_user=True
    ) -> None:
        super().__init__(ctx, name, description, use_user=use_user)

    def _team_text_termination(self) -> List[TextMentionTermination]:
        """
        初始化分诊环节的终止信号（条件）
        """
        return [
            TextMentionTermination(item.value)
            for item in PMCARoutingMessages.complex_executor_termination()
        ]

    def _team_max_turns(self) -> MaxMessageTermination:
        """
        初始化分诊环节的最大轮询次数（环境变量提供）
        """
        return MaxMessageTermination(self._ctx.task_env.TRIAGE_MAX_TURNS)

    async def _build_team_participants(self) -> None:
        """
        初始化分诊环节的参与智能体（ PMCATriage 和 PMCATriageReviewer ）
        """
        self._participants = []

        # 加入orchestrator智能体作为团队的整体决策者
        self._participants.append(
            self.ctx.assistant_factory.create_assistant(
                PMCACoreAssistants.ORCHESTRATOR.value
            )
        )

        if not self._user_proxy:
            raise ValueError("[复杂任务节点初始化阶段] 用户代理未能正常初始化")
        self._participants.append(self._user_proxy)

        triage_result = await self._ctx.task_workbench.get_item("triage_result")
        print(triage_result)

        for team_info in triage_result.get("team"):
            swarm_team_name = team_info.get("name")
            swarm_team_description = team_info.get("description")
            swarm_team = await PMCASwarm.create(
                self._ctx, swarm_team_name, swarm_team_description
            )
            self._participants.append(swarm_team.team)

        self._participants.append(
            self.ctx.assistant_factory.create_assistant(PMCACoreAssistants.TRIAGE.value)
        )
        self._participants.append(
            self.ctx.assistant_factory.create_assistant(
                PMCACoreAssistants.TRIAGE_REVIEWER.value
            )
        )

    def _build_team(self) -> Team:
        return SelectorGroupChat(
            self._participants,
            name="PMCA-RoundRobin-Triage",
            description="用户任务分诊器：根据用户任务描述决策任务的类型并提供团队初始化信息。",
            selector_prompt=PMCACOMPLEXTASK_SELECTORGROUP_SYSTEM_MESSAGE,
            allow_repeated_speaker=True,
            termination_condition=self._termination,
            model_client=self._ctx.llm_factory.client(),
        )
