from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class MessageType(str, Enum):
    """消息类型"""

    TEXT = "text"
    IMAGE = "image"
    CODE = "code"
    FILE = "file"
    SYSTEM = "system"


class BaseMessage(BaseModel):
    """基础消息类型"""

    content: str = Field(..., description="消息内容")
    sender: str = Field(..., description="消息发送者的ID或名字")
    receiver: str = Field(..., description="消息接收者的ID或名字")
    message_type: MessageType = Field(default=MessageType.TEXT, description="消息类型")


class CreateMessage(BaseMessage):
    """创建一个新消息的模式"""

    session_id: str = Field(..., description="会话的ID")
    parent_id: Optional[str] = Field(None, description="父进程的会话ID")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="消息元数据")
    attachments: List[Dict[str, Any]] = Field(
        default_factory=list, description="关联的文件或图像"
    )


class UpdateMessage(BaseModel):
    """更新一个消息的模式"""

    content: Optional[str] = Field(None, description="消息内容")
    metadata: Optional[Dict[str, Any]] = Field(None, description="消息元数据")
    is_edited: Optional[bool] = Field(None, description="消息是否更新过")


class Message(BaseMessage):
    """完整的消息模式"""

    id: str = Field(..., description="消息的唯一ID")
    session_id: str = Field(..., description="消息的会话ID")
    parent_id: Optional[str] = Field(None, description="父进程的会话ID(进程ID)")
    timestamp: datetime = Field(..., description="消息的发送时间")
    edited_time: Optional[datetime] = Field(None, description="消息最近一次修改的时间")
    is_edited: bool = Field(default=False, description="消息是否被修改过")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="消息的元数据")
    attachments: List[Dict[str, Any]] = Field(
        default_factory=list, description="消息关联的图像或文件"
    )

    class Config:
        """Pydantic configuration."""

        from_attributes = True
