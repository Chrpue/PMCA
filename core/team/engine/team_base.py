"""
Improved base class for PMCA multi‑agent teams.

This module refactors the existing PMCATeamBase to provide a more
predictable initialisation lifecycle, a unified run entry point and
better ergonomics for console vs. service modes.  It should be
integrated into your project by replacing uses of PMCATeamBase with
ImprovedTeamBase (or adapting the code pattern shown here).

Key features:
    * Explicit `initialize_team()` method to build the user proxy,
      participants, termination condition and team instance exactly
      once.  This removes hidden side‑effects from property getters.
    * A single `run_chat()` convenience method that inspects
      `ctx.task_env.INTERACTION_MODE` to choose between console and
      service modes, sets sensible defaults for `on_round`, and
      automatically falls back to the task mission stored in the
      context when no task is provided.
    * Retains compatibility with the existing `run()` signature by
      including `mode`, `background` and `on_round` parameters for
      static type checking.  The behaviour of these arguments is
      controlled by the `dispatch_run_mode` decorator defined in
      `core.team.engine.run_mode`.

This code is standalone and does not modify your existing files.  To
use it in your project, copy the class definition into the
appropriate module (replacing the old PMCATeamBase) and adjust
imports accordingly.
"""

from __future__ import annotations

import asyncio
import operator
from abc import ABC, abstractmethod
from functools import reduce
from typing import Any, AsyncGenerator, Callable, List, Optional, Sequence, Union

from autogen_agentchat.base import ChatAgent, Team, TaskResult
from autogen_agentchat.conditions import (
    ExternalTermination,
    MaxMessageTermination,
    TextMentionTermination,
)
from autogen_agentchat.messages import BaseAgentEvent, BaseChatMessage
from autogen_core import CancellationToken

from base.runtime.task_context import PMCATaskContext
from core.team.core_assistants import PMCAUserProxy
from core.team.engine.run_mode import dispatch_run_mode


class PMCATeamBase(ABC):
    """
    A refactored base class for PMCA teams.

    The class hides the complexity of initialising participants,
    termination conditions and the underlying team instance behind a
    single `initialize_team()` call.  The `run_chat()` method can
    then be used to run the team either in a console or service mode
    depending on the interaction mode declared in the runtime
    environment.
    """

    def __init__(self, ctx: PMCATaskContext) -> None:
        self._ctx = ctx
        self._team: Optional[Team] = None
        self._participants: List[ChatAgent | Team] = []
        self._termination: Optional[
            TextMentionTermination | ExternalTermination | MaxMessageTermination
        ] = None
        self._running_task: Optional[asyncio.Task] = None
        self._current_cancel_token: Optional[CancellationToken] = None
        self._external_termination: ExternalTermination = ExternalTermination()
        self._initialized: bool = False
        self._user_proxy: Optional[PMCAUserProxy] = None

    # -------------------------------------------------------------------------
    # Properties and helpers
    #
    # Although these properties lazily compute their values, the new
    # implementation recommends calling `initialize_team()` exactly once
    # before running the team.  This avoids repeated recomputation and
    # makes the control flow explicit.

    @property
    def ctx(self) -> PMCATaskContext:
        return self._ctx

    @property
    def user_proxy(self) -> PMCAUserProxy:
        """Return (and create if necessary) the user proxy used by this team."""
        if self._user_proxy is None:
            # Use the mission description from the context as the prompt when
            # available.  This will be shown when prompting the user for
            # input.  If no mission is provided, fall back to a generic
            # message.
            prompt = getattr(self._ctx, "task_mission", None)
            self._user_proxy = PMCAUserProxy(
                name="PMCAUserProxy",
                mode=self._ctx.task_env.INTERACTION_MODE,
                prompt_message=prompt
                or "请输入您的回复 (/cancel 取消, /pause 暂停, /interrupt <内容> 中断)",
            )
        return self._user_proxy

    async def initialize_team(self) -> None:
        """
        Build user proxy, participants, termination and team once.

        This method should be invoked before the first call to run or
        run_chat.  Subsequent invocations are no‑ops.
        """
        if self._initialized:
            return
        # Ensure user proxy is created
        _ = self.user_proxy
        # Create participants list using the subclass implementation
        self._participants = self._build_team_participants()
        # Build termination condition
        self._termination = self._combine_termination_condition()
        # Build team instance
        self._team = self._build_team()
        self._initialized = True

    @property
    def team(self) -> Team:
        if self._team is None:
            raise RuntimeError(
                "Team has not been initialised.  Call initialize_team() first."
            )
        return self._team

    @property
    def termination(self):
        if self._termination is None:
            self._termination = self._combine_termination_condition()
        return self._termination

    # -------------------------------------------------------------------------
    # Termination condition combination
    #
    def _combine_termination_condition(self):
        """Combine the external, max turns and text mention conditions."""
        # Gather the individual termination conditions
        text_terms = self._team_text_termination() or []
        parts = [self._external_termination, self._team_max_turns(), *text_terms]
        # Filter out any None values (in case a subclass returns None)
        active = [t for t in parts if t is not None]
        if not active:
            return None
        if len(active) == 1:
            return active[0]
        return reduce(operator.or_, active)

    # -------------------------------------------------------------------------
    # Abstract methods to be implemented by subclasses
    #
    @abstractmethod
    def _team_text_termination(self) -> List[TextMentionTermination]:
        """Return a list of termination conditions triggered by specific text"""
        raise NotImplementedError

    @abstractmethod
    def _team_max_turns(self) -> MaxMessageTermination:
        """Return a termination condition limiting the total number of messages"""
        raise NotImplementedError

    @abstractmethod
    def _build_team_participants(self) -> List[ChatAgent | Team]:
        """Construct and return the list of participants for this team"""
        raise NotImplementedError

    @abstractmethod
    def _build_team(self) -> Team:
        """Create and return the underlying team instance."""
        raise NotImplementedError

    # -------------------------------------------------------------------------
    # Core run logic
    #
    @dispatch_run_mode(mode_kw="mode", background_kw="background")
    async def run(
        self,
        *,
        task: Optional[Union[str, BaseChatMessage, Sequence[BaseChatMessage]]] = None,
        cancellation_token: Optional[CancellationToken] = None,
        output_task_messages: bool = True,
        # Note: the next three arguments are consumed by the run mode
        # decorator before this method executes.  They are only
        # included for static type checking and API clarity.
        mode: Optional[str] = None,
        background: bool = False,
        on_round: Optional[
            Callable[[int, List[Union[BaseAgentEvent, BaseChatMessage]]], Any]
        ] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[Union[BaseAgentEvent, BaseChatMessage, TaskResult], None]:
        """
        Low‑level run method.  It prepares the cancellation token and
        ensures initialisation.  Actual output dispatching is handled
        by the `dispatch_run_mode` decorator applied to this method.

        In most cases you should call `run_chat()` instead of this
        method directly.
        """
        if self._running_task is not None and not self._running_task.done():
            raise RuntimeError("团队组件已经在执行，在开启另一个执行过程前请先终止它.")
        # Set up a cancellation token.  If one is provided it will
        # propagate to user input and other awaiting tasks.
        self._current_cancel_token = cancellation_token or CancellationToken()

        # Initialise the team if necessary
        await self.initialize_team()

        # When no explicit task is provided on the first invocation,
        # use the mission string from the context.  Subsequent runs
        # (resume) may pass task=None to continue the conversation.
        effective_task = task
        if effective_task is None and not self._running_task:
            effective_task = getattr(self._ctx, "task_mission", None)

        # Delegate to the underlying team's run_stream.  The run mode
        # decorator will control the output behaviour (console vs
        # service) based on the `mode`, `background` and `on_round` kwargs.
        return self.team.run_stream(
            task=effective_task,
            cancellation_token=self._current_cancel_token,
            output_task_messages=output_task_messages,
        )

    async def run_chat(
        self,
        *,
        task: Optional[Union[str, BaseChatMessage, Sequence[BaseChatMessage]]] = None,
        background: bool = False,
        on_round: Optional[
            Callable[[int, List[Union[BaseAgentEvent, BaseChatMessage]]], Any]
        ] = None,
        output_task_messages: bool = True,
        mode: Optional[str] = None,
        **kwargs: Any,
    ) -> Any:
        """
        High‑level entry point to run the team.

        This method inspects the interaction mode from the runtime
        context (unless explicitly overridden via the `mode`
        parameter), sets up default behaviour for service mode, and
        invokes the underlying `run()` method decorated with
        `dispatch_run_mode`.  It returns either a TaskResult (for
        console mode) or a dictionary containing a list of rounds and
        the TaskResult (for service mode).

        :param task: initial task message(s) to start the conversation;
                     if omitted on first run, `ctx.task_mission` will
                     be used.
        :param background: if True in console mode, the console will
                           run in a background task and this method
                           will return an `asyncio.Task`.
        :param on_round: callback invoked after each round in service
                         mode; prints the round messages by default.
        :param output_task_messages: whether to include the original
                                     task message in the output stream.
        :param mode: override the interaction mode ('console' or
                     'service').  When None (default), the mode from
                     `ctx.task_env.INTERACTION_MODE` is used.
        """
        # Determine the effective run mode
        eff_mode = mode if mode is not None else self._ctx.task_env.INTERACTION_MODE
        # Provide a default round callback for service mode if none supplied
        eff_on_round = on_round
        if eff_mode == "service" and eff_on_round is None:

            def default_on_round(
                idx: int, msgs: List[Union[BaseAgentEvent, BaseChatMessage]]
            ) -> None:
                for m in msgs:
                    try:
                        text = m.to_text()
                    except Exception:
                        text = str(m)
                    sender = getattr(m, "source", "unknown")
                    print(f"[轮次 {idx}] {sender}: {text}")

            eff_on_round = default_on_round
        # Delegate to the run method (decorated) with explicit mode
        return await self.run(
            task=task,
            mode=eff_mode,
            background=background,
            on_round=eff_on_round,
            output_task_messages=output_task_messages,
            **kwargs,
        )
