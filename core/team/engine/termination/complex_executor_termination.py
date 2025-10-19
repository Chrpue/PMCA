import operator
from typing import Sequence, Optional, Tuple
from functools import reduce

from autogen_agentchat.base import TerminationCondition
from autogen_agentchat.conditions import (
    ExternalTermination,
    FunctionalTermination,
    MaxMessageTermination,
    SourceMatchTermination,
    TextMentionTermination,
)
from autogen_agentchat.messages import BaseAgentEvent, BaseChatMessage, StopMessage

from base.runtime.task_context import PMCATaskContext
from core.team.common.team_messages import PMCARoutingMessages
from core.team.core_assistants.core_assistants import PMCACoreAssistants


class PMCAComplexExecutorTermination:
    def __init__(self, ctx: PMCATaskContext) -> None:
        self._ctx = ctx

    def _functional_termination(
        self, messages: Sequence[BaseAgentEvent | BaseChatMessage]
    ) -> bool:
        return (
            PMCARoutingMessages.COMPLEX_EXECUTOR_SUCCESS.value in messages[-1].content  # type: ignore
            or PMCARoutingMessages.COMPLEX_EXECUTOR_FAILURE.value
            in messages[-1].content  # type: ignore
        )

    def termination(self):
        max_turns_termination = MaxMessageTermination(
            self._ctx.task_env.COMPLEX_EXECUTOR_MAX_TURNS
        )

        text_mention_termination = [
            TextMentionTermination(item.value)
            for item in PMCARoutingMessages.complex_executor_termination()
        ] or []

        text_mention_termination_or = (
            reduce(operator.or_, text_mention_termination)
            if text_mention_termination
            else None
        )

        orchestrator_only = SourceMatchTermination(
            [PMCACoreAssistants.ORCHESTRATOR.value]
        )

        if text_mention_termination_or is None:
            return max_turns_termination
        else:
            # (Max) OR ( TextMention AND SourceMatch(orchestrator) )
            return max_turns_termination | (
                text_mention_termination_or & orchestrator_only
            )
