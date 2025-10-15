from typing import Sequence, Optional, Any, Dict

from autogen_agentchat.base import TerminationCondition
from autogen_agentchat.conditions import (
    ExternalTermination,
    FunctionalTermination,
    MaxMessageTermination,
    TextMentionTermination,
)
from autogen_agentchat.messages import BaseAgentEvent, BaseChatMessage, StopMessage

from base.runtime.task_context import PMCATaskContext
from core.team.common.team_messages import PMCARoutingMessages


class PMCASwarmTermination:
    def __init__(self, ctx: PMCATaskContext) -> None:
        self._ctx = ctx

    def _functional_termination(
        self, messages: Sequence[BaseAgentEvent | BaseChatMessage]
    ) -> bool:
        return (
            PMCARoutingMessages.SWARM_SUCCESS.value in messages[-1].content  # type: ignore
            or PMCARoutingMessages.SWARM_FAILURE.value in messages[-1].content  # type: ignore
        )

    def termination(self):
        max_turns_termination = MaxMessageTermination(
            self._ctx.task_env.SWARM_MAX_TURNS
        )
        functional_termination = FunctionalTermination(self._functional_termination)

        return max_turns_termination | functional_termination
