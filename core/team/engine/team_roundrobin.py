from typing import List
from autogen_agentchat.base import ChatAgent, Team
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
from loguru import logger
from base.runtime.task_context import PMCATaskContext
from core.team.common.team_messages import PMCARoutingMessages
from core.team.core_assistants import PMCACoreAssistants
from core.team.engine.team_base import PMCATeamBase


class PMCARoundRobin(PMCATeamBase):
    def __init__(self, ctx: PMCATaskContext) -> None:
        super().__init__(ctx)

    def _team_text_termination(self) -> List[TextMentionTermination]:
        return [
            TextMentionTermination(item.value)
            for item in PMCARoutingMessages.roundrobin_termination()
        ]

    def _team_max_turns(self) -> MaxMessageTermination:
        return MaxMessageTermination(self._ctx.task_env.DECISION_MAX_TURNS)

    def _build_team_participants(self) -> List[ChatAgent | Team]:
        self._participants = []

        triage = self.ctx.assistant_factory.create_assistant(
            PMCACoreAssistants.TRIAGE.value
        )

        self._participants.append(self.user_proxy)
        self._participants.append(triage)

        return self._participants

    def _build_team(self) -> Team:
        return RoundRobinGroupChat(
            self.participants,
            termination_condition=self.termination,
        )
