"""
Message数据库模型
"""

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column

from database.db_model_base import DBModelBase


class Message(DBModelBase):
    """
    Message database model.

    Represents a message in a conversation.
    """

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False
    )

    content: Mapped[Text] = mapped_column(Text, nullable=False)
    role: Mapped[String] = mapped_column(
        String(50), nullable=False
    )  # user, assistant, system, etc.
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )

    # Optional metadata
    message_metadata: Mapped[JSON] = mapped_column(JSON, nullable=True)

    # Foreign keys
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent.id"), nullable=True
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("task.id"), nullable=True
    )

    # Timestamps
    created_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    agent = relationship("Agent", back_populates="messages")
    task = relationship("Task", back_populates="messages")

    def __repr__(self) -> str:
        """
        String representation of the Message.
        """
        return f"<Message {self.id} - {self.role}>"
