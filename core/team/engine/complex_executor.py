from typing import List
from autogen_agentchat.base import ChatAgent, Team
from autogen_agentchat.teams import RoundRobinGroupChat, SelectorGroupChat
from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
from loguru import logger
from base.prompts.complex_task import (
    PMCACOMPLEXTASK_SELECTORGROUP_SYSTEM_MESSAGE,
    PMCACOMPLEXTASK_ORCHESTRATOR_SYSTEM_MESSAGE,
)
from base.runtime.task_context import PMCATaskContext
from core.team.common.team_messages import PMCARoutingMessages
from core.team.core_assistants import PMCACoreAssistants
from core.assistant.factory import PMCAAssistantFactory
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
        return MaxMessageTermination(self._ctx.task_env.COMPLEX_EXECUTOR_MAX_TURNS)

    async def _build_team_participants(self) -> None:
        """
        初始化分诊环节的参与智能体（ PMCATriage 和 PMCATriageReviewer ）
        """

        if not self._user_proxy:
            raise ValueError("[复杂任务节点初始化阶段] 用户代理未能正常初始化")
        self._participants.append(self._user_proxy)

        triage_result = await self._ctx.task_workbench.get_item("triage_result")

        logger.success(f"**1**{self._participants}")

        self._participants = []

        system_message = self._build_orchestrator_system_prompt(triage_result)

        # 加入orchestrator智能体作为团队的整体决策者
        orchestrator = self.ctx.assistant_factory.create_assistant(
            PMCACoreAssistants.ORCHESTRATOR.value, system_message=system_message
        )

        self._participants.append(orchestrator)

        for team_info in triage_result.get("team"):
            swarm_team_name = team_info.get("name")
            swarm_team_description = team_info.get("description")
            swarm_team = await PMCASwarm.create(
                self._ctx, swarm_team_name, swarm_team_description
            )
            self._participants.append(swarm_team.team)

        logger.success(f"**2**{self._participants}")

    def _build_team(self) -> Team:
        return SelectorGroupChat(
            self._participants,
            name="PMCA-SELECTOR-GROUP-CHAT",
            description="根据用户任务和分诊结果完成复杂任务。",
            selector_prompt=PMCACOMPLEXTASK_SELECTORGROUP_SYSTEM_MESSAGE,
            allow_repeated_speaker=True,
            termination_condition=self._termination,
            model_client=self._ctx.llm_factory.client(),
        )

    def _build_orchestrator_system_prompt(self, triage_result) -> str:
        format_message = ""
        for index, team_info in enumerate(triage_result.get("team")):
            swarm_team_name = team_info.get("name")
            swarm_team_description = team_info.get("description")
            assistants = team_info.get("participants")

            format_message += f"执行团队{index + 1}:\n"
            format_message += f"- 团队名称: {swarm_team_name}\n"
            format_message += f"- 团队任务简要描述: {swarm_team_description}\n"
            format_message += "- 参与团队执行的智能体列表及其能力描述:\n"
            for jndex, assistant in enumerate(assistants):
                format_message += f"        - {PMCAAssistantFactory._registry[assistant].chinese_name}（{PMCAAssistantFactory._registry[assistant].name}）\n"
                format_message += (
                    f"        - {PMCAAssistantFactory._registry[assistant].duty}\n"
                )

        system_message = PMCACOMPLEXTASK_ORCHESTRATOR_SYSTEM_MESSAGE.format(
            task_triage_result=format_message
        )
        return system_message
