import uuid
from typing import Type
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, declared_attr
from sqlalchemy import DateTime, func


class DBModelBase(DeclarativeBase):
    """
    针对 PostgreSQL 优化的基础模型类 (CustomBase)
    所有 ORM 模型类可以继承此类并自动获得标准化字段
    """

    @declared_attr
    def __tablename__(cls: Type["DBModelBase"]) -> Mapped[str]:
        """
        自动生成表名__tablename__
        """
        return cls.__name__.lower()  # type: ignore

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False
    )
    created_time: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_time: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
