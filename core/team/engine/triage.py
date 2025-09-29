from typing import List
from autogen_agentchat.base import ChatAgent, Team
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
from base.runtime.task_context import PMCATaskContext
from core.team.common.team_messages import PMCARoutingMessages
from core.team.core_assistants import PMCACoreAssistants
from core.team.factory import PMCATeamFactory


class PMCATriageTeam(PMCATeamFactory):
    def __init__(
        self,
        ctx: PMCATaskContext,
        name: str,
        description: str,
        use_user: bool = False,
    ) -> None:
        super().__init__(ctx, name, description, use_user=use_user)

    def _team_text_termination(self) -> List[TextMentionTermination]:
        """
        初始化分诊环节的终止信号（条件）
        """
        return [
            TextMentionTermination(item.value)
            for item in PMCARoutingMessages.triage_termination()
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

        self._participants.append(
            self.ctx.assistant_factory.create_assistant(PMCACoreAssistants.TRIAGE.value)
        )
        self._participants.append(
            self.ctx.assistant_factory.create_assistant(
                PMCACoreAssistants.TRIAGE_REVIEWER.value
            )
        )
        self._participants

    def _build_team(self) -> Team:
        return RoundRobinGroupChat(
            self._participants,
            name="PMCA-RoundRobin-Triage",
            description="用户任务分诊器：根据用户任务描述决策任务的类型并提供团队初始化信息。",
            termination_condition=self._termination,
        )
