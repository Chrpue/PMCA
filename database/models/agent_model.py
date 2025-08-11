"""
Agent数据库模型
"""

import uuid
from datetime import datetime
from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column
from database.db_model_base import DBModelBase


class AgentModel(DBModelBase):
    """
    Agent database model.

    Represents an AI agent in the system.
    """

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False
    )
    name: Mapped[String] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Text] = mapped_column(Text, nullable=True)
    model: Mapped[String] = mapped_column(String(255), nullable=False)
    provider: Mapped[String] = mapped_column(String(255), nullable=False)
    system_prompt: Mapped[String] = mapped_column(Text, nullable=True)
    is_active: Mapped[String] = mapped_column(Boolean, default=True)
    created_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # 关系
    tasks = relationship("Task", back_populates="agent")
    messages = relationship("Message", back_populates="agent")

    def __repr__(self) -> str:
        """
        String representation of the Agent.
        """
        return f"<Agent {self.name}>"
