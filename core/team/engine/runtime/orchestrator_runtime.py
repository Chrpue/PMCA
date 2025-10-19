from __future__ import annotations
import asyncio

from loguru import logger
from dataclasses import asdict, is_dataclass
from typing import Any, Optional, Callable, Awaitable, TYPE_CHECKING

from autogen_core import (
    RoutedAgent,
    event,
    TypeSubscription,
    MessageContext,
    SingleThreadedAgentRuntime,
)
from autogen_core._agent_id import AgentId

from base.runtime.task_context import PMCATaskContext

from core.team.engine.event.swarm_event import SWARMStatusEvent, SWARMFinalEvent

if TYPE_CHECKING:
    try:
        from autogen_agentchat.agents import AssistantAgent
    except ImportError:
        AssistantAgent = object
else:
    AssistantAgent = object


class PMCAOrchestratorRuntime(RoutedAgent):
    """
    - 作为 Core 层订阅者（RoutedAgent），接收 swarm 包裹器通过 pub/sub 侧通道广播的执行事件；
    - 将事件以短历史形式写入任务工作台（ctx.task_workbench）；
    - 将事件转交给 orchestrator 本体 (AssistantAgent)，由其使用 Workbench(MCP) 完成 Redis 计划更新/再规划/收束。
    """

    def __init__(
        self,
        description: str,
        *,
        ctx: PMCATaskContext,
        orchestrator: AssistantAgent,
        max_inbox: int = 1000,
        workbench_prefix: str = "PMCAOrchestratorRuntime",
    ) -> None:
        super().__init__(description)
        self._ctx: PMCATaskContext = ctx
        self._orch: AssistantAgent = orchestrator
        self._max_inbox = max_inbox

        self._wb_key_status = f"{workbench_prefix}:status_events"
        self._wb_key_final = f"{workbench_prefix}:final_events"

        self._on_status_ext: Optional[
            Callable[[SWARMStatusEvent, MessageContext], Awaitable[None]]
        ] = None
        self._on_final_ext: Optional[
            Callable[[SWARMFinalEvent, MessageContext], Awaitable[None]]
        ] = None

    def set_on_status(
        self, fn: Callable[[SWARMStatusEvent, MessageContext], Awaitable[None]]
    ) -> None:
        self._on_status_ext = fn

    def set_on_final(
        self, fn: Callable[[SWARMFinalEvent, MessageContext], Awaitable[None]]
    ) -> None:
        self._on_final_ext = fn

    @staticmethod
    def _event_to_dict(evt: Any) -> dict[str, Any]:
        if is_dataclass(evt):
            return asdict(evt)
        if isinstance(evt, dict):
            return evt
        try:
            return dict(evt)  # type: ignore
        except Exception:
            return {"__repr__": repr(evt)}

    # ========== 工具：写入任务工作台（短历史裁剪） ==========
    async def _stash_to_workbench(self, key: str, item: Any) -> None:
        wb = getattr(self._ctx, "task_workbench", None)
        if wb and hasattr(wb, "get_item") and hasattr(wb, "set_item"):
            try:
                history = (await wb.get_item(key)) or []
                history.append(self._event_to_dict(item))
                if len(history) > self._max_inbox:
                    history = history[-self._max_inbox :]
                await wb.set_item(key, history)
            except Exception as e:
                logger.warning(
                    "[PMCAOrchestratorRuntime] workbench stash failed: %s", e
                )

    # ========== 工具：将事件转交 orchestrator 本体 ==========
    async def _forward_to_orchestrator(
        self, event: Any, core_ctx: MessageContext
    ) -> None:
        """
        约定优先：
          - 若 orchestrator 实现了 `async handle_swarm_event(event, ctx: PMCATaskContext)` -> 优先调用；
          - 否则若实现了 `async handle_swarm_event(event)` -> 退化调用；
          - 都没有则忽略（只完成 stash）。
        """
        handler = getattr(self._orch, "handle_swarm_event", None)
        if handler and asyncio.iscoroutinefunction(handler):
            try:
                try:
                    await handler(event, self._ctx)  # type: ignore[arg-type]
                except TypeError:
                    # 回退到 (event) 兼容签名
                    await handler(event)  # type: ignore[misc]
            except Exception as e:
                logger.exception(
                    "[PMCAOrchestratorRuntime] handle_swarm_event error: %s", e
                )

    # ========== 订阅处理：阶段状态（不中止） ==========
    @event
    async def on_status(
        self, message: SWARMStatusEvent, core_ctx: MessageContext
    ) -> None:
        """
        触发：swarm 包裹器在识别到中途状态（如 [ASSISTANT:OK/RETRY/NEEDUSER/IRRECOVERABLE]）
              后，发布 TopicId(type=\"pmca.status\", source=<task_id>) 时。
        流程：校验 → 写工作台短历史 → 外部钩子（可选）→ 转交 orchestrator。
        """
        # 轻校验（字段细则由发布方保障）
        if not getattr(message, "task_id", None) or not getattr(
            message, "routing", None
        ):
            logger.info(
                "[PMCAOrchestratorRuntime] ignore invalid status event: %r", message
            )
            return

        await self._stash_to_workbench(self._wb_key_status, message)

        if self._on_status_ext:
            try:
                await self._on_status_ext(message, core_ctx)
            except Exception as e:
                logger.exception(
                    "[PMCAOrchestratorRuntime] external on_status error: %s", e
                )

        await self._forward_to_orchestrator(message, core_ctx)

    # ========== 订阅处理：候选终结 ==========
    @event
    async def on_final(
        self, message: SWARMFinalEvent, core_ctx: MessageContext
    ) -> None:
        """
        触发：swarm 包裹器在识别到候选终结（如 [EXECUTE_SUCCESS/FAILURE/CANCEL]）
              后，发布 TopicId(type=\"pmca.final\", source=<task_id>) 时。
        流程：校验 → 写工作台短历史 → 外部钩子（可选）→ 转交 orchestrator。
        说明：是否真正终止团队，由 orchestrator 在被 selector 选中发言时产出硬信号（如 [ORCH_FINAL]）。
        """
        if not getattr(message, "task_id", None) or not getattr(
            message, "routing", None
        ):
            logger.info(
                "[PMCAOrchestratorRuntime] ignore invalid final event: %r", message
            )
            return

        await self._stash_to_workbench(self._wb_key_final, message)

        if self._on_final_ext:
            try:
                await self._on_final_ext(message, core_ctx)
            except Exception as e:
                logger.exception(
                    "[PMCAOrchestratorRuntime] external on_final error: %s", e
                )

        await self._forward_to_orchestrator(message, core_ctx)


async def register_orchestrator_runtime(
    runtime: SingleThreadedAgentRuntime,
    *,
    ctx: PMCATaskContext,
    orchestrator: AssistantAgent,
    agent_type: str = "PMCAOrchestrator",
    agent_key: Optional[str] = None,  # 可显式指定；不指定时建议用 ctx.task_id
    status_topic_type: str = "PMCA.STATUS",
    final_topic_type: str = "PMCA.FINAL",
    max_inbox: int = 1000,
) -> AgentId:
    """
    在 runtime 中注册本包裹器，并添加两条类型订阅，用于接收：
      - type=pmca.status → 阶段状态（不中止）
      - type=pmca.final  → 候选终结
    路由规则：topic.source 会作为 agent key；建议使用 task_id 作为 source 以天然隔离多任务。
    """
    key = agent_key or ctx.task_id

    await ctx.ensure_runtime_started()

    async def _factory() -> PMCAOrchestratorRuntime:
        return PMCAOrchestratorRuntime(
            description=f"PMCA Orchestrator Wrapper ({ctx.task_id})",
            ctx=ctx,
            orchestrator=orchestrator,
            max_inbox=max_inbox,
        )

    agent_id = await PMCAOrchestratorRuntime.register(runtime, agent_type, _factory)

    # 添加两条类型订阅：把对应 topic.type 的广播路由到本 agent_type
    await runtime.add_subscription(
        TypeSubscription(topic_type=status_topic_type, agent_type=agent_type)
    )
    await runtime.add_subscription(
        TypeSubscription(topic_type=final_topic_type, agent_type=agent_type)
    )

    return AgentId(type=agent_type, key=key)
