from __future__ import annotations

from dataclasses import dataclass, asdict, is_dataclass
from typing import Any, Dict, Optional, List


@dataclass
class PMCAEvent:
    topic_type: str = "PMCA:EVENT"
    task_id: str

    def to_dict(self) -> Dict[str, Any]:
        if is_dataclass(self):
            return asdict(self)
        try:
            return self.__dict__

        except Exception:
            return {"__repr__": repr(self)}


@dataclass
class TriageSummaryEvent(PMCAEvent):
    topic_type: str = "PMCA:TRIAGE"
    summary: str
    task_type: str
    confidence: float
    user_intent: Optional[str] = None
    constraints: List[str] = None
    artifacts: Dict[str, Any] = None
    metadata: Dict[str, Any] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary": self.summary,
            "task_type": self.task_type,
            "confidence": self.confidence,
            "user_intent": self.user_intent,
            "constraints": list(self.constraints),
            "artifacts": dict(self.artifacts),
            "metadata": dict(self.metadata),
            "task_id": self.task_id,
        }


@dataclass
class AssistantStatusEvent(PMCAEvent):
    topic_type: str = "PMCA:ASSISTANT:STATUS"
    assistant: str  # 事件来源（例如 PMCAOrchestrator、SwarmMemberA）
    node: Optional[str] = None  # 对应 GraphFlow 节点名称或模块
    stage: str  # 初始化 / 规划 / 执行 / 汇总 / 完成 等阶段标识
    status: str  # OK / RETRY / NEED_USER / FAILURE / IRRECOVERABLE
    progress: Optional[float] = None  # 任务进度百分比（0.0~1.0）
    message: Optional[str] = None  # 对当前阶段的简要说明
    need_user: bool = False  # 是否需要用户介入
    user_prompt: Optional[str] = None  # 需要用户提供的信息或操作提示
    payload: Optional[Dict[str, Any]] = None  # 附带的上下文数据或中间结果

    def to_dict(self) -> Dict[str, Any]:  # pragma: no cover - trivial
        return {
            "assistant": self.assistant,
            "node": self.node,
            "stage": self.stage,
            "status": self.status,
            "progress": self.progress,
            "need_user": self.need_user,
            "user_prompt": self.user_prompt,
            "message": self.message,
            "payload": self.payload or {},
            "task_id": self.task_id,
        }
