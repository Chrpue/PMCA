from __future__ import annotations

import asyncio
import operator
from abc import ABC, abstractmethod
from functools import reduce
from typing import (
    Any,
    AsyncGenerator,
    Callable,
    List,
    Mapping,
    Optional,
    Sequence,
    Union,
)

from autogen_agentchat.base import ChatAgent, Team, TaskResult
from autogen_agentchat.conditions import (
    ExternalTermination,
    MaxMessageTermination,
    TextMentionTermination,
)
from autogen_agentchat.messages import BaseAgentEvent, BaseChatMessage
from autogen_core import CancellationToken
from loguru import logger

from base.runtime.task_context import PMCATaskContext
from core.team.core_assistants import PMCAUserProxy
from core.team.engine.run_mode import dispatch_run_mode


def default_callable(
    idx: int, msgs: List[Union[BaseAgentEvent, BaseChatMessage]]
) -> None:
    for m in msgs:
        try:
            text = m.to_text()
        except Exception:
            text = str(m)
        sender = getattr(m, "source", "unknown")
        print(f"[轮次 {idx}] {sender}: {text}")


class PMCATeamFactory(ABC):
    def __init__(
        self,
        ctx: PMCATaskContext,
        name: str,
        description: str,
        *,
        use_user: bool = True,
    ) -> None:
        self._ctx = ctx
        self._name = name
        self._description = description
        self._use_user = use_user

        # 异步成员变量
        self._team: Team
        self._participants: List[ChatAgent | Team] = []

        # 不限制终结条件类型，方便子类扩展
        self._termination = None
        self._running_task: Optional[asyncio.Task] = None
        self._current_cancel_token: Optional[CancellationToken] = None
        self._external_termination: ExternalTermination = ExternalTermination()
        self._initialized: bool = False
        self._user_proxy: Optional[PMCAUserProxy] = None

    @classmethod
    async def create(
        cls, ctx: PMCATaskContext, name: str, description: str, *, use_user: bool = True
    ) -> "PMCATeamFactory":
        """
        异步工厂方法。
        创建并完全初始化一个团队实例，确保返回的对象立即可用。
        """
        instance = cls(ctx, name, description, use_user=use_user)
        await instance._async_init()
        return instance

    async def _async_init(self) -> None:
        if self._use_user:
            self._user_proxy = PMCAUserProxy(self._ctx)
        await self._build_team_participants()
        self._termination = self._combine_termination_condition()
        self._team = self._build_team()

    @property
    def ctx(self) -> PMCATaskContext:
        return self._ctx

    @property
    def user_proxy(self) -> Optional[PMCAUserProxy]:
        if self._use_user and self._user_proxy is None:
            self._user_proxy = PMCAUserProxy(
                self._ctx,
            )
        return self._user_proxy

    @property
    def team(self) -> Team:
        assert self._team is not None, (
            "团队组件还未初始化. 使用 `await YourTeam.create(...)`."
        )
        return self._team

    def _combine_termination_condition(self):
        text_terms = self._team_text_termination() or []
        parts = [self._external_termination, self._team_max_turns(), *text_terms]
        active = [t for t in parts if t is not None]
        if not active:
            return None
        if len(active) == 1:
            return active[0]
        return reduce(operator.or_, active)

    @abstractmethod
    def _team_text_termination(self) -> List[TextMentionTermination]:
        """Return a list of termination conditions triggered by specific text"""
        raise NotImplementedError

    @abstractmethod
    def _team_max_turns(self) -> MaxMessageTermination:
        """Return a termination condition limiting the total number of messages"""
        raise NotImplementedError

    @abstractmethod
    async def _build_team_participants(self) -> None:
        """Construct and return the list of participants for this team"""
        raise NotImplementedError

    @abstractmethod
    def _build_team(self) -> Team:
        """Create and return the underlying team instance."""
        raise NotImplementedError

    async def reset(self) -> None:
        """
        重置团队状态，在任务被取消或完全结束后时调用
        """
        await self.team.reset()

    async def pause(self) -> Mapping[str, Any]:
        """
        暂停团队并保存其当前状态
        """
        if not self._initialized:
            raise RuntimeError("无法在未初始化的团队上进行暂停操作.")
        await self.team.pause()
        print("团队已暂停，正在保存状态...")
        state = await self.team.save_state()
        print("保存成功...")
        return state

    async def resume(self, **kwargs) -> Any:
        """
        恢复团队运行
        """
        print("正在从状态快照加载团队...")
        # await self.team.load_state(state)
        print("状态加载完成，正在恢复团队...")
        await self.team.resume()
        print("团队已恢复，继续执行任务...")

        return await self.discuss(task=None, **kwargs)

    @dispatch_run_mode
    async def run(
        self,
        *,
        task: Optional[Union[str, BaseChatMessage, Sequence[BaseChatMessage]]] = None,
        cancellation_token: Optional[CancellationToken] = None,
        output_task_messages: bool = True,
        **kwargs: Any,
    ) -> AsyncGenerator[Union[BaseAgentEvent, BaseChatMessage, TaskResult], None]:
        if self._running_task is not None and not self._running_task.done():
            raise RuntimeError("团队组件已经在执行，在开启另一个执行过程前请先终止它.")

        self._current_cancel_token = cancellation_token or CancellationToken()

        effective_task = task
        if effective_task is None and not self._running_task:
            effective_task = getattr(self._ctx, "task_mission", None)

        return self.team.run_stream(
            task=effective_task,
            cancellation_token=self._current_cancel_token,
            output_task_messages=output_task_messages,
        )

    async def discuss(
        self,
        *,
        task: Optional[Union[str, BaseChatMessage, Sequence[BaseChatMessage]]] = None,
        background: Optional[bool] = None,
        custom_callable: Optional[Callable] = None,
        output_task_messages: bool = True,
        mode: Optional[str] = None,
        **kwargs: Any,
    ) -> Any:
        """
        高级入口，负责从环境变量和参数中确定最终的运行配置。
        """

        effective_mode = mode
        if effective_mode is None:
            effective_mode = self._ctx.task_env.INTERACTION_MODE or "console"

        effective_background = background
        if effective_background is None:
            effective_background = self._ctx.task_env.RUN_BACKGROUND or False

        effective_callable = custom_callable
        if effective_mode == "service" and effective_callable is None:
            effective_callable = default_callable

        return await self.run(
            task=task,
            mode=effective_mode,
            background=effective_background,
            custom_callable=effective_callable,
            output_task_messages=output_task_messages,
            **kwargs,
        )
