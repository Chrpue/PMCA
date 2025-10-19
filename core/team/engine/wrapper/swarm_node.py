from __future__ import annotations

from typing import Sequence, AsyncGenerator, Union, Optional, Any
from dataclasses import asdict, is_dataclass
import json
import re
from uuid import uuid4

from loguru import logger
from autogen_agentchat.agents import BaseChatAgent
from autogen_agentchat.base import TaskResult, Response
from autogen_agentchat.messages import (
    BaseChatMessage,
    BaseAgentEvent,
    TextMessage,
)
from autogen_core import CancellationToken, TopicId, SingleThreadedAgentRuntime

from base.runtime.task_context import PMCATaskContext
from core.team.factory import PMCATeamFactory

from core.team.engine.event.swarm_event import SWARMStatusEvent, SWARMFinalEvent
from utils.somehandler import swarm_name_to_snake, make_valid_identifier


def _to_jsonable(obj: Any) -> Any:
    if hasattr(obj, "model_dump") and callable(getattr(obj, "model_dump")):
        try:
            return obj.model_dump()
        except Exception:
            try:
                return obj.dict()  # type: ignore[attr-defined]
            except Exception:
                return str(obj)
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    if isinstance(obj, dict):
        return {str(k): _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(v) for v in obj]
    # dataclass / 其它对象兜底
    if is_dataclass(obj):
        try:
            return asdict(obj)
        except Exception:
            return str(obj)
    return str(obj)


def _simplify_messages(
    msgs: Optional[Sequence[Union[BaseAgentEvent, BaseChatMessage]]],
) -> list[dict]:
    """
    轻量化团队讨论消息，专注 ChatMessage；事件默认跳过，避免把 token/chunk 等噪音写入。
    """
    out: list[dict] = []
    if not msgs:
        return out
    for m in msgs:
        if not isinstance(m, BaseChatMessage):
            continue
        try:
            content = _to_jsonable(getattr(m, "content", None))
            created_at = getattr(m, "created_at", None)
            created_at_str = created_at.isoformat() if created_at else None
            out.append(
                _to_jsonable(
                    {
                        "source": getattr(m, "source", None),
                        "type": getattr(m, "type", None),
                        "content": content,
                        "created_at": created_at_str,
                    }
                )
            )
        except Exception as e:
            logger.warning(f"[swarm_node] simplify message failed: {e}")
            out.append(
                {
                    "source": getattr(m, "source", None),
                    "type": getattr(m, "type", None),
                    "content": str(getattr(m, "content", None)),
                }
            )
    return out


def _last_text_from_messages(
    msgs: Optional[Sequence[Union[BaseAgentEvent, BaseChatMessage]]],
) -> Optional[str]:
    if not msgs:
        return None
    for m in reversed(msgs):
        if isinstance(m, TextMessage) and m.content:
            return m.content
    return None


def _detect_swarm_signal(text: Optional[str]) -> str:
    """
    识别 swarm 团队上报信号（文本层面）：
    - [REPORT_FINAL]   → [SWARM_FINAL]
    - [REPORT_STATUS]  → [SWARM_STATUS]
    - 否则             → [SWARM_DONE]
    """
    if not text:
        return "[SWARM_DONE]"
    t = text.strip().upper()
    if "[REPORT_FINAL]" in t:
        return "[SWARM_FINAL]"
    if "[REPORT_STATUS]" in t:
        return "[SWARM_STATUS]"
    return "[SWARM_DONE]"


def _sanitize_source(s: str) -> str:
    """只允许字母、数字、下划线、连字符（与底层 name/source 约束一致）"""
    s = re.sub(r"[^A-Za-z0-9_-]", "_", s)
    return s[:64]


def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


class PMCASwarmWrapper(BaseChatAgent):
    """
    Swarm 团队包裹器：
    - 流式：中途事件透传；末尾落盘 transcript（可选键前缀）并上报最小信号
    - 非流式：一次性返回同样的“最小信号”，并落盘 transcript
    - 只传“新增消息”，上下文由团队/代理维持
    """

    def __init__(
        self,
        ctx: PMCATaskContext,
        team: PMCATeamFactory,
        runtime: SingleThreadedAgentRuntime,
        name: str = "PMCASwarmTeamWrapper",
        description: str = "Wrapper agent for swarm team",
        *,
        transcript_key: Optional[str] = None,
    ) -> None:
        super().__init__(name=make_valid_identifier(name), description=description)
        self._ctx = ctx
        self._team = team
        self._runtime = runtime
        self._transcript_key = transcript_key or "swarm_transcript"
        self._status_topic_type = "PMCA.STATUS"
        self._final_topic_type = "PMCA.FINAL"

    @property
    def produced_message_types(self):
        return [TextMessage]

    async def on_messages_stream(
        self,
        messages: Sequence[BaseChatMessage],
        cancellation_token: CancellationToken,
    ) -> AsyncGenerator[Union[BaseAgentEvent, BaseChatMessage, Response], None]:
        effective_task: Optional[Sequence[BaseChatMessage]] = messages or None
        logger.debug(f"[{self.name}] swarm stream start, new_messages={len(messages)}")

        # 只调工厂 discuss（它返回 DualUseStream），严格对齐 run_stream 契约：
        stream = await self._team.discuss(
            task=effective_task,
            output_task_messages=True,
        )

        async for item in stream:
            if isinstance(item, TaskResult):
                # 1) 轻量化 transcript 并入库（JSON 友好化 + 试探序列化）
                transcript = _simplify_messages(item.messages)
                try:
                    _ = json.dumps(transcript, ensure_ascii=False)
                    await self._ctx.task_workbench.set_item(
                        self._transcript_key, transcript
                    )
                    logger.debug(
                        f"[{self.name}] stored {self._transcript_key} ({len(transcript)})"
                    )
                except Exception as e:
                    logger.warning(
                        f"[{self.name}] store {self._transcript_key} failed: {e}"
                    )

                # 2) 上报“最小信号”作为 Response（供上层路由/调度）
                last_text = _last_text_from_messages(item.messages)
                signal = _detect_swarm_signal(last_text)
                yield Response(
                    chat_message=TextMessage(source=self.name, content=signal)
                )
            else:
                # 中途事件原样透传（Console/前端各自消费）
                yield item

    # ------- 非流式：少量需要一次性结果的地方 -------
    async def on_messages(
        self,
        messages: Sequence[BaseChatMessage],
        cancellation_token: CancellationToken,
    ) -> Response:
        effective_task: Optional[Sequence[BaseChatMessage]] = messages or None
        logger.debug(
            f"[{self.name}] swarm non-stream start, new_messages={len(messages)}"
        )

        result: TaskResult = await self._team.discuss(
            task=effective_task,
            output_task_messages=True,
        )

        transcript = _simplify_messages(result.messages)
        try:
            _ = json.dumps(transcript, ensure_ascii=False)
            await self._ctx.task_workbench.set_item(self._transcript_key, transcript)
            logger.debug(
                f"[{self.name}] stored {self._transcript_key} ({len(transcript)})"
            )
        except Exception as e:
            logger.warning(f"[{self.name}] store {self._transcript_key} failed: {e}")

        last_text = _last_text_from_messages(result.messages)
        signal = _detect_swarm_signal(last_text)
        return Response(chat_message=TextMessage(source=self.name, content=signal))

    async def on_reset(self, cancellation_token: CancellationToken) -> None:
        logger.debug(f"[{self.name}] reset")
        await self._team.reset()

    async def _emit_events_from_result(self, result: TaskResult) -> None:
        """
        按照“最小上报流”设计：
        - 如果最后文本含 [REPORT_FINAL] → 发布 SWARMFinalEvent 到 PMCA.FINAL
        - 如果最后文本含 [REPORT_STATUS] → 发布 SWARMStatusEvent 到 PMCA.STATUS
        - 其它情况 → 可选：发一个 SWARMStatusEvent([SWARM_DONE])，或不发（这里选择“发”，便于 OrchestratorRuntime 也能记录一次收束）
        """
        last_text = _last_text_from_messages(result.messages)
        signal = _detect_swarm_signal(last_text)

        # 构造通用字段
        task_id = self._ctx.task_id
        caller = self.name
        ts = _now_iso_utc()
        eid = str(uuid4())

        try:
            if signal == "[SWARM_FINAL]":
                evt = SWARMFinalEvent(
                    routing="[EXECUTE_SUCCESS]",
                    task_id=task_id,
                    caller=caller,
                    summary=last_text or "",
                    timestamp=ts,
                    event_id=eid,
                    step_hint=None,  # TODO: 如需编码“当前子任务标签”可在此留痕
                )
                await self._runtime.publish_message(
                    evt,
                    topic_id=TopicId(
                        type=self._final_topic_type, source=_sanitize_source(task_id)
                    ),
                )
                logger.debug(f"[{self.name}] published FINAL event: {eid}")

            else:
                # STATUS（含 SWARM_STATUS / SWARM_DONE）
                routing = (
                    "[ASSISTANT:OK]"
                    if signal == "[SWARM_STATUS]"
                    else "[ASSISTANT:DONE]"
                )
                evt = SWARMStatusEvent(
                    routing=routing,
                    task_id=task_id,
                    caller=caller,
                    summary=last_text or "",
                    timestamp=ts,
                    event_id=eid,
                    step_hint=None,
                )
                await self._runtime.publish_message(
                    evt,
                    topic_id=TopicId(
                        type=self._status_topic_type, source=_sanitize_source(task_id)
                    ),
                )
                logger.debug(f"[{self.name}] published STATUS event: {eid}")

        except Exception as e:
            # 广播是单向的；失败只记日志不反压
            logger.warning(f"[{self.name}] publish event failed: {e}")
