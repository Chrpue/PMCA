from __future__ import annotations
from typing import Any, Dict, Optional, Sequence, Union

from autogen_agentchat.base import TerminationCondition
from autogen_agentchat.messages import (
    BaseAgentEvent,
    BaseChatMessage,
    FunctionExecutionResult,
)
from autogen_core.models import FunctionExecutionResultMessage
from autogen_agentchat.messages import (
    StopMessage,
)

FINAL_TOOL_NAMES = {"report_final"}


def _parse_result_content(content: Any) -> Dict[str, Any]:
    """content 可能是 JSON 字符串或已是 dict；统一返回 dict（尽量稳健）。"""
    if isinstance(content, dict):
        return content
    if isinstance(content, str):
        import json

        try:
            return json.loads(content)
        except Exception:
            return {"text": content}
    try:
        import json

        return json.loads(str(content))
    except Exception:
        return {"text": str(content)}


class PMCAFinalTerminationCondition(TerminationCondition):
    """
    命中条件：本轮增量消息中存在 MCP 工具 `report_final/pmca_emit_final` 的执行结果。
    终止行为：StopMessage(content=<你全局约定的 [] 终止标记，例如 "[EXECUTE_SUCCESS]">)
    """

    def __init__(self, task_id: str | None = None) -> None:
        super().__init__()
        self.task_id = task_id

    def _is_final_reason(self, reason: str) -> bool:
        return reason.startswith("[EXECUTE_") and reason.endswith("]")

    def _scan_delta(
        self, delta: Sequence[Union[BaseAgentEvent, BaseChatMessage]]
    ) -> Optional[StopMessage]:
        for msg in reversed(delta):
            if not isinstance(msg, FunctionExecutionResultMessage):
                continue

            results = list(msg.content or [])
            for r in reversed(results):
                if not isinstance(r, FunctionExecutionResult):
                    continue

                name = getattr(r, "name", None)
                data = _parse_result_content(getattr(r, "content", None))
                evt = data.get("event", data) if isinstance(data, dict) else {}

                if self.task_id and isinstance(evt, dict):
                    tid = evt.get("task_id")
                    if tid and tid != self.task_id:
                        continue

                if name in FINAL_TOOL_NAMES:
                    reason = (evt or {}).get("reason")
                    if isinstance(reason, str) and self._is_final_reason(reason):
                        return StopMessage(
                            content=reason, source="PMCAFinalTermination"
                        )

                reason = (evt or {}).get("reason")
                if isinstance(reason, str) and self._is_final_reason(reason):
                    return StopMessage(content=reason, source="PMCAFinalTermination")

        return None

    async def __call__(
        self, messages: Sequence[BaseChatMessage]
    ) -> Optional[StopMessage]:
        return self._scan_delta(messages)
