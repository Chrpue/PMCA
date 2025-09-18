from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, Optional

from autogen_core import CancellationToken
from autogen_agentchat.agents import UserProxyAgent
from core.team.common import PMCARoutingMessages


class PMCAUserProxy(UserProxyAgent):
    """
    一个增强的用户代理：通过 input_func 实现 console / service 双模式复用。
    - console: 终端阻塞输入（可被 CancellationToken 取消）
    - service: 非阻塞，立即返回“需要用户介入”信号
    """

    def __init__(
        self,
        name: str = "PMCAUserProxy",
        *,
        # get_mode: Callable[[], str] | None = None,
        mode: str = "console",
        console_input: Callable[[str, Optional[CancellationToken]], Awaitable[str]]
        | None = None,
        service_input: Callable[[str, Optional[CancellationToken]], Awaitable[str]]
        | None = None,
        description: str = "一个用户代理，负责处理需要人类介入的场景。",
    ):
        # self._get_mode = get_mode or (lambda: "console")
        self._mode = mode
        self._console_input = console_input or self._default_console_input
        self._service_input = service_input or self._default_service_input

        async def _mux(
            prompt: str, cancellation_token: Optional[CancellationToken] = None
        ) -> str:
            mode = self._mode.lower()
            if mode == "console":
                return await self._console_input(prompt, cancellation_token)
            return await self._service_input(prompt, cancellation_token)

        super().__init__(name=name, description=description, input_func=_mux)

    # ---- 默认 console 逻辑：在后台线程调用 input()，并与 CancellationToken 关联 ----
    async def _default_console_input(
        self, prompt: str, cancellation_token: Optional[CancellationToken]
    ) -> str:
        """
        通过 asyncio.to_thread 包装 input()，并把 Task 与 CancellationToken 关联；
        若被取消，返回一个取消信号（你也可以选择直接 raise）。
        """
        task = asyncio.create_task(asyncio.to_thread(input, f"{prompt}\n> "))
        if cancellation_token:
            cancellation_token.link_future(
                task
            )  # token.cancel() -> task.cancel() 直接生效。:contentReference[oaicite:10]{index=10}

        try:
            user_input = await task
        except asyncio.CancelledError:
            # 你也可以改为：raise 让上层感知 CancelledError
            return PMCARoutingMessages.SIGNAL_CANCEL.value

        user_input = (user_input or "").strip()
        lower_input = user_input.lower()

        if lower_input == "/cancel":
            return PMCARoutingMessages.SIGNAL_CANCEL.value
        if lower_input == "/pause":
            return PMCARoutingMessages.SIGNAL_PAUSE.value
        if lower_input.startswith("/interrupt"):
            parts = user_input.split(" ", 1)
            if len(parts) > 1 and parts[1].strip():
                return f"{PMCARoutingMessages.SIGNAL_INTERRUPT_PREFIX.value} {parts[1].strip()}"
        return user_input

    # ---- 默认 service 逻辑：不阻塞，直接把控制权交回应用层 ----
    async def _default_service_input(
        self, prompt: str, cancellation_token: Optional[CancellationToken]
    ) -> str:
        # Web 服务里通常希望“停下并把控制权交给前端/业务”
        # 这里返回一个固定信号，让上层捕获并暂停/持久化，再等待用户输入后 resume。
        return PMCARoutingMessages.TEAM_NEED_USER.value
