from typing import List
from loguru import logger
from autogen_agentchat.base import ChatAgent, Team
from autogen_agentchat.teams import RoundRobinGroupChat, Swarm
from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
from base.runtime.task_context import PMCATaskContext
from core.team.common.team_messages import PMCARoutingMessages
from core.team.core_assistants import PMCACoreAssistants
from core.team.factory import PMCATeamFactory


class PMCASwarm(PMCATeamFactory):
    def __init__(
        self,
        ctx: PMCATaskContext,
        name: str,
        description: str,
        use_user: bool = False,
    ) -> None:
        super().__init__(ctx, name, description, use_user=use_user)
        self._first_speaker_name = None

    def _team_text_termination(self) -> List[TextMentionTermination]:
        """
        初始化分诊环节的终止信号（条件）
        """
        return [
            TextMentionTermination(item.value)
            for item in PMCARoutingMessages.swarm_termination()
        ]

    def _team_max_turns(self) -> MaxMessageTermination:
        """
        初始化分诊环节的最大轮询次数（环境变量提供）
        """
        return MaxMessageTermination(self._ctx.task_env.SWARM_MAX_TURNS)

    async def _build_team_participants(self) -> None:
        """
        初始化 swarm 团队的参与智能体（ 视分诊结果决定 ）
        """
        self._participants = []

        triage_result = await self._ctx.task_workbench.get_item("triage_result")
        triage_team_list = triage_result.get("team")
        for team_item in triage_team_list:
            if team_item.get("name") == self._name:
                swarm_participants = team_item.get("participants")
                self._first_speaker_name = swarm_participants[0]
                for name in swarm_participants:
                    dynamic_handoffs = [
                        p_name for p_name in swarm_participants if p_name != name
                    ]
                    assistant = self._ctx.assistant_factory.create_assistant(
                        name, dynamic_hadoffs=dynamic_handoffs or None
                    )
                    self._participants.append(assistant)
                break

        first_speaker = next(
            p for p in self._participants if p.name == self._first_speaker_name
        )

        self._participants.remove(first_speaker)
        self._participants.insert(0, first_speaker)

        self._participants

    def _build_team(self) -> Team:
        participants_list = [
            assistant
            for assistant in self._participants
            if isinstance(assistant, ChatAgent)
        ]
        return Swarm(
            participants=participants_list,
            name=self._name,
            description=self._description,
            termination_condition=self._termination,
        )
