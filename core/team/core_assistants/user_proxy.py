"""
Enhanced PMCAUserProxy implementation.

This module refactors the existing PMCAUserProxy to allow custom
prompts, centralise the command parsing logic and maintain a clean
separation between the user interface and the team runtime.  It
demonstrates how to implement the input function expected by
`autogen_agentchat.agents.UserProxyAgent` using plain `input()`
instead of relying on Rich or other external UI libraries.

Key improvements:
    * Accepts a `prompt_message` parameter which, if provided, will
      be displayed to the user instead of the internal prompt passed
      in by the team.  This allows the team (or the context) to
      customise how the user is prompted.
    * The console input function prints a helpful instruction line
      showing available commands (`/cancel`, `/pause`, `/interrupt`),
      then uses `asyncio.to_thread(input, ...)` to capture
      synchronous input without blocking the event loop.  It
      automatically links the input task to a `CancellationToken`,
      enabling immediate cancellation when the team is stopped.
    * Returns special signal strings (from `PMCARoutingMessages`) for
      commands, which can be captured by `TextMentionTermination`
      conditions in the team.  This decouples the user proxy from
      direct knowledge of team methods like `cancel_now()`.

To use this class, copy the code into `core/team/core_assistants/user_proxy.py`
or import it alongside your existing user proxies.  Instantiate it by
passing `mode` and `prompt_message` from your task context.
"""

from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, Optional

from autogen_core import CancellationToken
from autogen_agentchat.agents import UserProxyAgent

from core.team.common.team_messages import PMCARoutingMessages


class PMCAUserProxy(UserProxyAgent):
    """
    A refined user proxy agent which supports console and service modes
    and allows a custom prompt to be displayed to the user.

    :param name: Name of the agent
    :param mode: Interaction mode ('console' or 'service')
    :param prompt_message: A string to show to the user when
                           requesting input; if None, the default
                           prompt passed by the team will be used.
    :param console_input: Optional override for the console input
                          function.  Must be an async function with
                          signature `(prompt: str, cancellation_token: Optional[CancellationToken]) -> str`.
    :param service_input: Optional override for the service mode input
                          function.  Must be an async function with the
                          same signature.
    :param description: Human‑readable description of the agent.
    """

    def __init__(
        self,
        name: str = "PMCAUserProxy",
        *,
        mode: str = "console",
        prompt_message: Optional[str] = None,
        console_input: Optional[
            Callable[[str, Optional[CancellationToken]], Awaitable[str]]
        ] = None,
        service_input: Optional[
            Callable[[str, Optional[CancellationToken]], Awaitable[str]]
        ] = None,
        description: str = "一个用户代理，负责处理需要人类介入的场景。",
    ):
        self._mode = (mode or "console").lower()
        self._prompt_message = prompt_message
        self._console_input = console_input or self._default_console_input
        self._service_input = service_input or self._default_service_input

        async def _mux(
            prompt: str, cancellation_token: Optional[CancellationToken] = None
        ) -> str:
            # Choose the input function based on the current mode
            if self._mode == "console":
                return await self._console_input(prompt, cancellation_token)
            return await self._service_input(prompt, cancellation_token)

        super().__init__(name=name, description=description, input_func=_mux)

    # ------------------------------------------------------------------
    # Default input handlers
    #
    async def _default_console_input(
        self, prompt: str, cancellation_token: Optional[CancellationToken]
    ) -> str:
        """
        Prompt the user for input in console mode.

        This implementation displays a custom prompt (if provided) and
        a list of available commands before capturing input using
        `input()`.  It runs `input()` in a thread via
        `asyncio.to_thread` to avoid blocking the event loop and links
        the task to the cancellation token so that pending input can
        be cancelled immediately.
        """
        # Build the message shown to the user.  Use the custom prompt
        # when available; otherwise fall back to the prompt provided by
        # the team.
        display_prompt = self._prompt_message or prompt
        instruction = (
            "\n" + display_prompt + "\n"
            "可输入以下命令:\n"
            "  /cancel   —— 取消并终止当前任务\n"
            "  /pause    —— 暂停当前任务，稍后可恢复\n"
            "  /interrupt <内容> —— 中断并提供新的上下文\n"
            "> "
        )
        # Launch synchronous input in a thread to avoid blocking.  We
        # capture the task so that we can link it to the cancellation
        # token.
        task = asyncio.create_task(asyncio.to_thread(input, instruction))
        if cancellation_token:
            # Link the token so that token.cancel() will cancel the
            # input task.  The behaviour of link_future() is such that
            # when the token is cancelled, the task is cancelled as well.
            cancellation_token.link_future(task)
        try:
            user_input = await task
        except asyncio.CancelledError:
            # If the input task is cancelled, return a cancellation
            # signal so that the team can react accordingly.
            return PMCARoutingMessages.SIGNAL_CANCEL.value

        user_input = (user_input or "").strip()
        lower_input = user_input.lower()
        # Interpret special commands by returning signal strings.  The
        # team should include these signals in its text‑mention
        # termination conditions.
        if lower_input == "/cancel":
            return PMCARoutingMessages.SIGNAL_CANCEL.value
        if lower_input == "/pause":
            return PMCARoutingMessages.SIGNAL_PAUSE.value
        if lower_input.startswith("/interrupt"):
            parts = user_input.split(" ", 1)
            if len(parts) > 1 and parts[1].strip():
                return f"{PMCARoutingMessages.SIGNAL_INTERRUPT_PREFIX.value} {parts[1].strip()}"
        # Otherwise return the raw user input
        return user_input

    async def _default_service_input(
        self, prompt: str, cancellation_token: Optional[CancellationToken]
    ) -> str:
        """
        Immediately return a special signal to indicate that user
        intervention is required.  The calling code should react to
        this signal by pausing the team and awaiting further input
        through another mechanism (e.g. a web form).
        """
        return PMCARoutingMessages.TEAM_NEED_USER.value
