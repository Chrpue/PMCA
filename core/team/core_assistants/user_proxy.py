from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, List, Optional, Dict

from autogen_core import CancellationToken
from autogen_agentchat.agents import BaseChatAgent, UserProxyAgent
from loguru import logger

# 假设 PMCARoutingMessages 存在且定义了 các 信号
from base.runtime.task_context import PMCATaskContext
from core.team.common.team_messages import PMCARoutingMessages

DEFAULT_CONSOLE_COMMANDS = {
    "cancel": "/cancel",
    "pause": "/pause",
    "interrupt": "/interrupt",
}


class PMCAUserProxy(UserProxyAgent):
    def __init__(
        self,
        ctx: PMCATaskContext,
        *,
        console_input: Optional[
            Callable[[str, Optional[CancellationToken]], Awaitable[str]]
        ] = None,
        service_input: Optional[
            Callable[[str, Optional[CancellationToken]], Awaitable[str]]
        ] = None,
        description: str = "一个用户代理，负责处理需要人类介入的场景。",
    ):
        self._name: str = "PMCAUserProxy"
        self._ctx = ctx
        self._mode = ctx.task_env.INTERACTION_MODE

        # --- 优化点 3: 应用可配置的命令 ---
        self._console_commands = DEFAULT_CONSOLE_COMMANDS.copy()

        self._mode_map = {
            "console": console_input or self._default_console_input,
            "service": service_input or self._default_service_input,
        }

        async def _mux(
            prompt: str, cancellation_token: Optional[CancellationToken] = None
        ) -> str:
            handler = self._mode_map.get(self._mode)
            if not handler:
                raise ValueError(
                    f"不支持的交互模式: {self._mode} 请检查环境变量 .env 中的配置信息。"
                )
            return await handler(prompt, cancellation_token)

        super().__init__(name=self._name, description=description, input_func=_mux)

    def register_input_mode(
        self, mode_name: str, handler: Callable[..., Awaitable[str]]
    ):
        """
        公开一个方法，用于在运行时注册新的输入模式处理器。
        这使得类的扩展性极强。
        """
        self._mode_map[mode_name.lower()] = handler

    async def _default_console_input(
        self, prompt: str, cancellation_token: Optional[CancellationToken]
    ) -> str:
        """
        在控制台模式下提示用户输入。
        此方法现在只负责核心的I/O逻辑：构建提示、非阻塞地获取输入、并处理取消。
        命令解析的职责被移交给了 _parse_console_commands 方法。
        """
        cmd_cancel = self._console_commands.get("cancel", "/cancel")
        cmd_pause = self._console_commands.get("pause", "/pause")
        cmd_interrupt = self._console_commands.get("interrupt", "/interrupt")

        instruction = (
            f"*********************************************************************************************************************\n"
            f"1.[{cmd_cancel}]-取消并终止当前任务  2.[{cmd_pause}]-暂停当前任务  3.[{cmd_interrupt} <补充内容>]-中断并提供新的上下文\n"
            f"*********************************************************************************************************************\n"
            "可输入以下命令:\n"
            "> "
        )

        task = asyncio.create_task(asyncio.to_thread(input, instruction))
        if cancellation_token:
            cancellation_token.link_future(task)
        try:
            user_input = await task
            self._ctx.task_mission = user_input
        except asyncio.CancelledError:
            return PMCARoutingMessages.SIGNAL_CANCEL.value

        return self._parse_console_commands(user_input)

    async def _default_service_input(
        self, prompt: str, cancellation_token: Optional[CancellationToken]
    ) -> str:
        return "服务方法还未实现"

    def _parse_console_commands(self, user_input: str) -> str:
        """
        专门负责解析来自控制台的原始输入字符串。
        它将特殊命令翻译成内部信号，否则返回原始输入。
        """
        stripped_input = (user_input or "").strip()
        lower_input = stripped_input.lower()

        cmd_cancel = self._console_commands.get("cancel", "/cancel")
        cmd_pause = self._console_commands.get("pause", "/pause")
        cmd_interrupt = self._console_commands.get("interrupt", "/interrupt")

        if lower_input == cmd_cancel:
            return PMCARoutingMessages.SIGNAL_CANCEL.value
        if lower_input == cmd_pause:
            return PMCARoutingMessages.SIGNAL_PAUSE.value

        if lower_input.startswith(cmd_interrupt):
            parts = stripped_input.split(" ", 1)
            if len(parts) > 1 and parts[1].strip():
                content = parts[1].strip()
                return f"{PMCARoutingMessages.SIGNAL_INTERRUPT_PREFIX.value} {content}"

        return stripped_input
