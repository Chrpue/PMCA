from typing import List
from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
from base.runtime.task_context import PMCATaskContext
from core.team.common.team_messages import PMCARoutingMessages
from core.team.core_assistants.user_proxy import PMCAUserProxy
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

    async def _build_team_participants(self):
        raise NotImplementedError

    def _build_team(self):
        raise NotImplementedError
