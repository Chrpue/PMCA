import operator
from typing import Sequence
from functools import reduce
from autogen_agentchat.conditions import (
    MaxMessageTermination,
    TextMentionTermination,
)

from base.runtime.task_context import PMCATaskContext
from core.team.common.team_messages import PMCARoutingMessages


class PMCATriageTermination:
    def __init__(self, ctx: PMCATaskContext) -> None:
        self._ctx = ctx

    def termination(self):
        max_turns_termination = MaxMessageTermination(
            self._ctx.task_env.TRIAGE_MAX_TURNS
        )

        text_mention_termination = [
            TextMentionTermination(item.value)
            for item in PMCARoutingMessages.triage_termination()
        ] or []
        terminations = [max_turns_termination, *text_mention_termination]
        active = [t for t in terminations if t is not None]

        if not active:
            return None
        if len(active) == 1:
            return active[0]
        return reduce(operator.or_, active)
