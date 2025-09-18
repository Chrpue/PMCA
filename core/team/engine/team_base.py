import asyncio
import operator
from functools import reduce
from abc import ABC, abstractmethod
from typing import AsyncGenerator, Callable, List, Optional, Sequence, Union, Any

from autogen_agentchat.conditions import (
    ExternalTermination,
    MaxMessageTermination,
    TextMentionTermination,
)
from autogen_core import CancellationToken
from loguru import logger
from base.runtime.task_context import PMCATaskContext
from autogen_agentchat.messages import BaseAgentEvent, BaseChatMessage
from autogen_agentchat.base import ChatAgent, Team, TaskResult

from core.team.common import PMCARoutingMessages
from core.team.core_assistants import PMCAUserProxy
from core.team.engine.run_mode import dispatch_run_mode


class PMCATeamBase(ABC):
    def __init__(self, ctx: PMCATaskContext) -> None:
        self._ctx = ctx
        self._running_task: Optional[asyncio.Task] = None
        self._current_cancel_token: Optional[CancellationToken] = None
        self._external_termination: ExternalTermination = ExternalTermination()
        self._team: Optional[Team] = None
        self._user_proxy: Optional[PMCAUserProxy] = None
        self._termination = None
        self._participants: List[ChatAgent | Team] = []

    @property
    def ctx(self):
        return self._ctx

    def initialize_team(self):
        _ = self.user_proxy

    @property
    def user_proxy(self):
        if self._user_proxy is None:
            self._user_proxy = PMCAUserProxy(
                name="PMCAUserProxy", mode=self._ctx.task_env.INTERACTION_MODE
            )
        return self._user_proxy

    @property
    def participants(self):
        if not self._participants:
            self._participants = self._build_team_participants()
        return self._participants

    @property
    def team(self):
        if self._team is None:
            self._team = self._build_team()
        return self._team

    @property
    def termination(self):
        if self._termination is None:
            self._termination = self._combine_termination_condition()
        return self._termination

    @abstractmethod
    def _team_text_termination(self) -> List[TextMentionTermination]:
        raise NotImplementedError

    @abstractmethod
    def _team_max_turns(self) -> MaxMessageTermination:
        raise NotImplementedError

    @abstractmethod
    def _build_team_participants(self) -> List[ChatAgent | Team]:
        raise NotImplementedError

    @abstractmethod
    def _build_team(self):
        raise NotImplementedError

    def _combine_termination_condition(self):
        return (
            self._external_termination
            | self._team_max_turns()
            | reduce(operator.or_, self._team_text_termination())
        )

    @dispatch_run_mode(mode_kw="mode", background_kw="background")
    async def run(
        self,
        *,
        task: Optional[Union[str, BaseChatMessage, Sequence[BaseChatMessage]]] = None,
        cancellation_token: Optional[CancellationToken] = None,
        output_task_messages: bool = False,
    ) -> AsyncGenerator[Union[BaseAgentEvent, BaseChatMessage, TaskResult], None]:
        if self._running_task is not None and not self._running_task.done():
            raise RuntimeError("团队组件已经在执行，在开启另一个执行过程前请先终止它.")

        self._current_cancel_token = cancellation_token or CancellationToken()

        if not self.team:
            raise RuntimeError(
                "Team 尚未构建，请先调用 _build_team() 初始化 self._team."
            )
        return self.team.run_stream(
            task=task,
            cancellation_token=self._current_cancel_token,
            output_task_messages=output_task_messages,
        )

    async def request_pause(self) -> None:
        """
        触发优雅暂停（ExternalTermination）：等待当前说话轮结束后停止。
        建议在 Web UI “暂停”按钮调用它；随后可再次 run/run_stream 继续
        """
        self._external_termination.set()

    def cancel_now(self) -> None:
        """
        立即中断（CancellationToken）。注意这可能让 Team 处于不一致状态；
        官方建议仅在“紧急停止”时使用，常规请用 request_pause()。:contentReference[oaicite:6]{index=6}
        """
        if self._current_cancel_token:
            self._current_cancel_token.cancel()

    async def _team_reset(self) -> None:
        """尽管官方在 run 停止后会自动 reset，这里提供显式 reset 以满足工程稳健性。"""
        if not self._team:
            return
        await self._team.reset()

    # async def run_console(
    #     self,
    #     *,
    #     task: Optional[Union[str, BaseChatMessage, Sequence[BaseChatMessage]]] = None,
    #     background: bool = False,
    #     **kwargs: Any,
    # ):
    #     """等价于 run(mode='console', ...)"""
    #     return await self.run(
    #         task=task,
    #         mode="console",  # type: ignore
    #         background=background,  # type: ignore
    #         **kwargs,
    #     )
    #
    # async def run_service(
    #     self,
    #     *,
    #     task: Optional[Union[str, BaseChatMessage, Sequence[BaseChatMessage]]] = None,
    #     on_round: Optional[
    #         Callable[[int, List[Union[BaseAgentEvent, BaseChatMessage]]], Any]
    #     ] = None,
    #     **kwargs: Any,
    # ):
    #     """等价于 run(mode='service', on_round=..., ...)"""
    #     return await self.run(
    #         task=task,
    #         mode="service",  # type: ignore
    #         on_round=on_round,  # type: ignore
    #         **kwargs,
    #     )

    async def run_auto(
        self,
        *,
        task: Optional[Union[str, BaseChatMessage, Sequence[BaseChatMessage]]] = None,
        background=False,
        on_round=None,
        **kwargs,
    ):
        mode = self.ctx.task_env.INTERACTION_MODE
        return await self.run(
            task=task, mode=mode, background=background, on_round=on_round, **kwargs
        )
