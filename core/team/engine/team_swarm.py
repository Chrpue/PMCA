from typing import List

from autogen_agentchat.base import ChatAgent
from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
from base.runtime import PMCATaskContext
from core.team.common.team_messages import PMCARoutingMessages
from .team_base import PMCATeamBase


class PMCASwarmTeam(PMCATeamBase):
    def __init__(self, ctx: PMCATaskContext) -> None:
        super().__init__(ctx)

    def _team_text_termination(self) -> List[TextMentionTermination]:
        return [
            TextMentionTermination(item.value)
            for item in PMCARoutingMessages.swarm_termination()
        ]

    def _team_max_turns(self) -> MaxMessageTermination:
        return MaxMessageTermination(self._ctx.task_env.SWARM_MAX_TURNS)

    def _initial_speaker(self):
        pass

    async def _build_team_participants(self):
        participants: List[ChatAgent] = []
        decision_result = await self._ctx.task_workbench.get_item("TASK_DECISION")

    def _build_team(self):
        raise NotImplementedError
