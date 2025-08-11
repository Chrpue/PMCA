from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class BaseAgentSchema(BaseModel):
    """基础智能体模式"""

    name: str = Field(..., description="智能体名称")
    description: str = Field(..., description="智能体能力描述")
    capabilities: List[str] = Field(
        default_factory=list, description="智能体的能力列表"
    )


class AgentSchema(BaseAgentSchema):
    """智能体模式"""

    id: str = Field(..., description="智能体的唯一标识ID")
    model: str = Field(..., description="智能体基于的模型")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="模型参数")
    created_time: datetime = Field(..., description="智能体的创建时间")
    updated_time: datetime = Field(..., description="智能体最后更新的时间")

    class Config:
        """Pydantic configuration."""

        from_attributes = True


class AgentCreateSchema(BaseAgentSchema):
    """构建新智能体"""

    model: str = Field(..., description="智能体基于的模型")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="模型参数")


class AgentUpdateSchema(BaseModel):
    """更新智能体"""

    name: Optional[str] = Field(None, description="智能体名称")
    description: Optional[str] = Field(None, description="智能体的能力描述")
    capabilities: Optional[List[str]] = Field(None, description="智能体能力列表")
    model: Optional[str] = Field(None, description="智能体基于的模型")
    parameters: Optional[Dict[str, Any]] = Field(None, description="模型参数")
