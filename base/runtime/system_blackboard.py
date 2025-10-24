from __future__ import annotations

import asyncio
from dataclasses import dataclass, asdict, is_dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional, Type

from autogen_core import (
    RoutedAgent,
    event,
    TypeSubscription,
    MessageContext,
    SingleThreadedAgentRuntime,
    TopicId,
)
from autogen_core._agent_id import AgentId

from .task_context import PMCATaskContext
from .event.system_event import PMCAEvent


class BlackboardStorage:
    def __init__(self, max_len: int = 100) -> None:
        self._store: Dict[str, List[Dict[str, Any]]] = {}
        self._max_len = max_len

    async def append(self, key: str, value: Dict[str, Any]) -> None:
        hist = self._store.setdefault(key, [])
        hist.append(value)
        if len(hist) > self._max_len:
            del hist[0 : len(hist) - self._max_len]

    async def get_all(self, key: str) -> List[Dict[str, Any]]:
        return list(self._store.get(key, []))

    async def get_latest(self, key: str) -> Optional[Dict[str, Any]]:
        hist = self._store.get(key)
        return hist[-1] if hist else None


class PMCABlackboardManager:
    def __init__(self, ctx: PMCATaskContext, *, enable_storage: bool = True) -> None:
        self._ctx = ctx
        self._runtime: SingleThreadedAgentRuntime = ctx.task_runtime
        self._enable_storage = enable_storage
        self._registered: bool = False
        self._event_types: Dict[str, Type[PMCAEvent]] = {}
        self._on_receive: Optional[
            Callable[[PMCAEvent, MessageContext], Awaitable[None]]
        ] = None

    def register_event_type(self, event_cls: Type[PMCAEvent]) -> None:
        """
        为黑板注册事件类型
        """
        if not hasattr(event_cls, "topic_type"):
            raise ValueError(
                f"Event class {event_cls} must define a 'topic_type' attribute"
            )
        self._event_types[event_cls.topic_type] = event_cls

    def set_on_receive(
        self, fn: Callable[[PMCAEvent, MessageContext], Awaitable[None]]
    ) -> None:
        """ """
        self._on_receive = fn

    async def publish(self, pmca_event: PMCAEvent) -> None:
        """
        发布事件到黑板
        """
        await self._ctx.ensure_runtime_started()
        topic = TopicId(type=pmca_event.topic_type, source=pmca_event.task_id)
        await self._runtime.publish_message(pmca_event, topic_id=topic)

    async def _store_event(self, pmca_event: PMCAEvent) -> None:
        if not self._enable_storage:
            return
        wb = self._ctx.task_workbench
        key = f"blackboard:{pmca_event.topic_type}"
        try:
            history: List[Dict[str, Any]] = (await wb.get_item(key)) or []
            history.append(pmca_event.to_dict())
            # Keep only the most recent 500 events per type to bound memory
            if len(history) > 500:
                history = history[-500:]
            await wb.set_item(key, history)
        except Exception as exc:
            try:
                from loguru import logger  # type: ignore

                logger.warning(
                    f"[Blackboard] failed to store event {pmca_event}: {exc}"
                )
            except Exception:
                print(f"[Blackboard] failed to store event {pmca_event}: {exc}")

    async def register_runtime(
        self,
        agent_type: str = "PMCABlackboard",
        agent_key: Optional[str] = None,
        *,
        max_inbox: int = 1000,
    ) -> AgentId:
        if self._registered:
            raise RuntimeError("Blackboard runtime already registered")

        await self._ctx.ensure_runtime_started()
        key = agent_key or self._ctx.task_id

        async def _factory() -> PMCABlackboardRuntime:
            return PMCABlackboardRuntime(
                description=f"PMCA Blackboard ({self._ctx.task_id})",
                manager=self,
                max_inbox=max_inbox,
            )

        registerad_agent_type = await PMCABlackboardRuntime.register(
            self._runtime, agent_type, _factory
        )

        # 为每一种事件创建类型订阅模式
        for topic_type in self._event_types.keys():
            await self._runtime.add_subscription(
                TypeSubscription(topic_type=topic_type, agent_type=agent_type)
            )

        self._registered = True
        return AgentId(type=registerad_agent_type, key=key)


class PMCABlackboardRuntime(RoutedAgent):
    """
    黑板运行时：负责接收和处理黑板事件
    """

    def __init__(
        self,
        description: str,
        *,
        manager: PMCABlackboardManager,
        max_inbox: int = 1000,
    ) -> None:
        super().__init__(description)
        self._manager = manager
        self._max_inbox = max_inbox
        # Keep a bounded queue of recently received events (optional)
        self._inbox: List[PMCAEvent] = []

    async def _on_event_received(self, event: PMCAEvent, ctx: MessageContext) -> None:
        """
        黑板事件统一入口
        """
        self._inbox.append(event)
        if len(self._inbox) > self._max_inbox:
            self._inbox = self._inbox[-self._max_inbox :]

        await self._manager._store_event(event)

        if self._manager._on_receive:
            try:
                await self._manager._on_receive(event, ctx)
            except Exception as exc:
                try:
                    from loguru import logger  # type: ignore

                    logger.exception(
                        f"[BlackboardRuntime] on_receive hook error: {exc}"
                    )
                except Exception:
                    print(f"[BlackboardRuntime] on_receive hook error: {exc}")

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        cls._generated_handlers: List[str] = []

    @classmethod
    def generate_handlers(cls, event_types: Dict[str, Type[PMCAEvent]]) -> None:
        """
        为每个 PMCA 事件类型创建事件处理程序方法。
        AutoGen 使用 ``@event`` 装饰器将函数注册为消息处理程序。由于我们无法在实例创建时动态应用装饰器，因此我们使用
        ``setattr`` 将它们添加到类定义中。此方法必须在注册黑板代理之前调用。对于给定的子类，它是幂等的。
        """
        for topic_type, event_cls in event_types.items():
            method_name = f"on_{topic_type.lower().replace('.', '_')}"
            if hasattr(cls, method_name):
                continue

            async def handler(self, message: event_cls, ctx: MessageContext) -> None:  # type: ignore
                await self._on_event_received(message, ctx)

            decorated = event(handler)
            setattr(cls, method_name, decorated)
            cls._generated_handlers.append(method_name)
