from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

from .task_context import PMCATaskContext


class BlackboardCondition:
    def __init__(
        self,
        topic_type: str,
        predicate: Callable[[Dict[str, Any]], bool],
        *,
        timeout: float = 0.0,
        poll_interval: float = 0.2,
    ) -> None:
        self.topic_type = topic_type
        self.predicate = predicate
        self.timeout = timeout
        self.poll_interval = poll_interval

    async def __call__(self, ctx: PMCATaskContext) -> bool:
        """Evaluate the predicate against the latest event.

        If ``timeout`` > 0, this method waits for up to ``timeout``
        seconds for an event of the specified type to appear in the
        workbench.  If no event is found after the timeout, the
        condition returns ``False``.
        """

        async def get_latest() -> Optional[Dict[str, Any]]:
            try:
                key = f"BLACKBOARD:{self.topic_type}"
                return await ctx.task_workbench.get_item(key)  # type: ignore[attr-defined]
            except Exception:
                return None

        async def evaluate(event: Optional[Dict[str, Any]]) -> bool:
            if not event:
                return False
            try:
                return bool(self.predicate(event))
            except Exception:
                return False

        # If no wait is requested, check once and return
        if self.timeout <= 0:
            event = await get_latest()
            return await evaluate(event)

        # Otherwise poll until a matching event or timeout
        deadline = asyncio.get_event_loop().time() + self.timeout
        while True:
            event = await get_latest()
            if await evaluate(event):
                return True
            if asyncio.get_event_loop().time() >= deadline:
                return False
            await asyncio.sleep(self.poll_interval)


class RouterPolicy:
    """Implements a simple conditional router over multiple branches.

    A ``RouterPolicy`` holds an ordered list of condition/target pairs.
    When ``decide`` is called, each condition is awaited in sequence
    and, if it evaluates to ``True``, the corresponding target name is
    returned.  If no conditions match, ``RuntimeError`` is raised.
    """

    def __init__(self) -> None:
        self._rules: List[Tuple[Callable[[PMCATaskContext], Awaitable[bool]], str]] = []

    def when(
        self, condition: Callable[[PMCATaskContext], Awaitable[bool]], goto: str
    ) -> RouterPolicy:
        """Add a routing rule.

        Parameters
        ----------
        condition: Callable[[PMCATaskContext], Awaitable[bool]]
            A coroutine that evaluates to ``True`` when this route
            should be taken.

        goto: str
            The name or identifier of the next node to execute if the
            condition matches.

        Returns
        -------
        RouterPolicy
            The router itself for fluent chaining.
        """
        self._rules.append((condition, goto))
        return self

    async def decide(self, ctx: PMCATaskContext) -> str:
        """Evaluate routing rules and return the first matching target.

        Parameters
        ----------
        ctx: PMCATaskContext
            The task context from which blackboard events will be read.

        Returns
        -------
        str
            The name of the next node to execute.

        Raises
        ------
        RuntimeError
            If none of the conditions match.
        """
        for cond, target in self._rules:
            try:
                if await cond(ctx):
                    return target
            except Exception:
                # Skip faulty conditions
                continue
        raise RuntimeError("RouterPolicy: no rule matched")
