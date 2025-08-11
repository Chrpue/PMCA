"""
Task数据库模型
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Enum, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column

from database.db_model_base import DBModelBase


class TaskStatus(enum.Enum):
    """
    Task status enum.
    """

    PENDING = "pending"
    PROGRESSING = "progressing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Task(DBModelBase):
    """
    Task database model.

    Represents a task assigned to an agent.
    """

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False
    )
    title: Mapped[Text] = mapped_column(String(255), nullable=False)
    description: Mapped[Text] = mapped_column(Text, nullable=True)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus), default=TaskStatus.PENDING, nullable=False
    )

    # 任务输入和输出
    input_data: Mapped[JSON] = mapped_column(JSON, nullable=True)
    output_data: Mapped[JSON] = mapped_column(JSON, nullable=True)

    # 外键
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent.id"), nullable=False
    )
    parent_task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("task.id"), nullable=True
    )

    # Timestamps
    created_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    # 关系
    agent = relationship("Agent", back_populates="tasks")
    messages = relationship("Message", back_populates="task")
    subtasks = relationship("Task", backref="parent_task", remote_side=[id])

    def __repr__(self) -> str:
        """
        String representation of the Task.
        """
        return f"<Task {self.title} - {self.status.value}>"
