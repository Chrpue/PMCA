from __future__ import annotations

import json
from typing import Sequence, AsyncGenerator, Union, Optional, Any

from loguru import logger
from autogen_agentchat.agents import BaseChatAgent
from autogen_agentchat.base import TaskResult, Response
from autogen_agentchat.messages import (
    BaseChatMessage,
    BaseAgentEvent,
    TextMessage,
)
from autogen_core import CancellationToken

from base.runtime.task_context import PMCATaskContext
from core.team.factory import PMCATeamFactory
from core.team.common.team_messages import PMCARoutingMessages

from base.runtime.event import AssistantStatusEvent, TriageSummaryEvent


def _to_jsonable(obj: Any) -> Any:
    """把任意对象转为 JSON 友好的类型。"""
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

    return str(obj)


def _simplify_messages(
    msgs: Optional[Sequence[Union[BaseAgentEvent, BaseChatMessage]]],
) -> list[dict]:
    """
    将团队讨论消息轻量化，便于存储到 workbench。
    - 仅保留 ChatMessage（事件默认跳过，避免把 token/chunk 等噪音写入）
    - 对 content 做 JSON 化处理，解决 MemoryContent 等不可序列化问题
    """
    out: list[dict] = []
    if not msgs:
        return out
    for m in msgs:
        if not isinstance(m, BaseChatMessage):
            continue
        try:
            content = getattr(m, "content", None)
            content = _to_jsonable(content)

            created_at = getattr(m, "created_at", None)
            created_at_str = created_at.isoformat() if created_at else None

            item = {
                "source": getattr(m, "source", None),
                "type": getattr(m, "type", None),
                "content": content,
                "created_at": created_at_str,
            }
            out.append(_to_jsonable(item))
        except Exception as e:
            out.append(
                {
                    "source": getattr(m, "source", None),
                    "type": getattr(m, "type", None),
                    "content": str(getattr(m, "content", None)),
                }
            )
            logger.warning(f"simplify message failed: {e}")
    return out


class PMCATriageTeamWrapper(BaseChatAgent):
    """
    分诊团队的包装器：
    - 流式：透传中途事件；末尾仅产出路由标记
    - 同时在末尾把本轮分诊讨论 transcript 轻量化后写入 workbench['triage_transcript']
    - 非流式：同理，仅返回路由标记并写入 transcript
    - 上下文连续：每一轮仅把“新增消息”作为 task 传入，团队内部维护对话状态
    """

    def __init__(
        self,
        ctx: PMCATaskContext,
        team: PMCATeamFactory,
        name: str = "PMCATriageTeamWrapper",
        description: str = "Wrapper agent for triage team",
    ) -> None:
        super().__init__(name=name, description=description)
        self._ctx = ctx
        self._team = team

    @property
    def produced_message_types(self):
        return [TextMessage]

    # 流式方法
    async def on_messages_stream(
        self,
        messages: Sequence[BaseChatMessage],
        cancellation_token: CancellationToken,
    ) -> AsyncGenerator[Union[BaseAgentEvent, BaseChatMessage, Response], None]:
        effective_task: Optional[Sequence[BaseChatMessage]] = messages or None
        logger.debug(f"[{self.name}] triage stream start, new_messages={len(messages)}")

        stream = await self._team.discuss(
            task=effective_task,
            output_task_messages=True,
        )

        async for item in stream:
            if isinstance(item, TaskResult):
                transcript = _simplify_messages(item.messages)

                try:
                    _ = json.dumps(transcript, ensure_ascii=False)
                    await self._ctx.task_workbench.set_item(
                        "triage_transcript", transcript
                    )
                    logger.debug(
                        f"[{self.name}] stored triage_transcript ({len(transcript)})"
                    )
                except Exception as e:
                    logger.warning(f"[{self.name}] store triage_transcript failed: {e}")

                stop = item.stop_reason or ""
                if PMCARoutingMessages.TRIAGE_SUCCESS.value in stop:
                    content = PMCARoutingMessages.TRIAGE_SUCCESS.value
                    status_flag = "SUCCESS"
                else:
                    content = PMCARoutingMessages.TRIAGE_FAILURE.value
                    status_flag = "FAILURE"

                logger.debug(f"[{self.name}] triage stream end -> {content}")

                try:
                    bb = getattr(self._ctx, "blackboard", None)
                    task_id = getattr(self._ctx, "task_id", None)
                    if bb and task_id:
                        evt = AssistantStatusEvent(
                            task_id=task_id,
                            assistant=self.name,
                            node="triage",
                            stage="complete",
                            status=status_flag,
                            progress=1.0,
                            need_user=False,
                            message=f"Triage completed with status {status_flag}",
                        )
                        await bb.publish(evt)
                except Exception as e:
                    logger.warning(
                        f"[{self.name}] publish AssistantStatusEvent failed: {e}"
                    )

                yield Response(
                    chat_message=TextMessage(source=self.name, content=content)
                )
            else:
                yield item

    # 非流式（少数需要一次性结果的地方）
    async def on_messages(
        self,
        messages: Sequence[BaseChatMessage],
        cancellation_token: CancellationToken,
    ) -> Response:
        effective_task: Optional[Sequence[BaseChatMessage]] = messages or None
        logger.debug(
            f"[{self.name}] triage non-stream start, new_messages={len(messages)}"
        )

        result: TaskResult = await self._team.discuss(
            task=effective_task,
            output_task_messages=True,
        )

        transcript = _simplify_messages(result.messages)
        try:
            _ = json.dumps(transcript, ensure_ascii=False)
            await self._ctx.task_workbench.set_item("triage_transcript", transcript)
            logger.debug(f"[{self.name}] stored triage_transcript ({len(transcript)})")
        except Exception as e:
            logger.warning(f"[{self.name}] store triage_transcript failed: {e}")

        stop = result.stop_reason or ""
        if PMCARoutingMessages.TRIAGE_SUCCESS.value in stop:
            content = PMCARoutingMessages.TRIAGE_SUCCESS.value
        else:
            content = PMCARoutingMessages.TRIAGE_FAILURE.value

        logger.debug(f"[{self.name}] triage non-stream end -> {content}")
        return Response(chat_message=TextMessage(source=self.name, content=content))

    async def on_reset(self, cancellation_token: CancellationToken) -> None:
        logger.debug(f"[{self.name}] reset")
        await self._team.reset()
