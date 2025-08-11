from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """任务状态"""

    PENDING = "pending"
    PROGRESSING = "progressing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BaseTask(BaseModel):
    """任务基础模式"""

    title: str = Field(..., description="任务名称")
    description: str = Field(..., description="任务的详细描述")
    assigned_agent: Optional[str] = Field(None, description="任务指派给的智能体ID")


class CreateTask(BaseTask):
    """创建新任务的模式"""

    priority: int = Field(default=1, description="任务优先级(1-5)")
    deadline: Optional[datetime] = Field(None, description="任务要求执行的最后时间限制")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="任务的元数据")


class UpdateTask(BaseModel):
    """更新已存在任务的模式"""

    title: Optional[str] = Field(None, description="任务名称")
    description: Optional[str] = Field(None, description="任务的详细描述")
    status: Optional[TaskStatus] = Field(None, description="当前任务的执行状态")
    assigned_agent: Optional[str] = Field(None, description="任务指派给的智能体ID")
    priority: Optional[int] = Field(None, description="任务优先级(1-5)")
    deadline: Optional[datetime] = Field(None, description="任务要求执行的最后时间限制")
    metadata: Optional[Dict[str, Any]] = Field(None, description="任务元数据")
    results: Optional[Any] = Field(None, description="任务执行结果")


class Task(BaseTask):
    """完整的任务模式"""

    id: str = Field(..., description="任务的唯一标识ID")
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="当前任务的状态")
    priority: int = Field(default=1, description="任务的优先级(1-5)")
    deadline: Optional[datetime] = Field(None, description="任务要求执行的最后时间限制")
    created_time: datetime = Field(..., description="任务创建的时间")
    updated_time: datetime = Field(..., description="任务更新的时间")
    completed_time: Optional[datetime] = Field(None, description="任务完成的时间")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="任务元数据")
    results: Optional[Any] = Field(None, description="任务执行结果")

    class Config:
        """Pydantic configuration."""

        from_attributes = True
