from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Optional, Callable, Awaitable


@dataclass
class SWARMStatusEvent:
    # 中途状态（不中止）：[ASSISTANT:OK] / [ASSISTANT:RETRY] / [ASSISTANT:NEEDUSER] / [ASSISTANT:IRRECOVERABLE]
    routing: str
    task_id: str
    caller: str
    summary: str
    timestamp: str
    event_id: str
    step_hint: Optional[str] = None


@dataclass
class SWARMFinalEvent:
    # 候选终结（可触发 Selector 终止）：[EXECUTE_SUCCESS] / [EXECUTE_FAILURE] / [EXECUTE_CANCEL]
    routing: str
    task_id: str
    caller: str
    summary: str
    timestamp: str
    event_id: str
    step_hint: Optional[str] = None
