from typing import List, Optional
from pydantic import BaseModel, Field


class PMCAAssistantDomain(BaseModel):
    """
    定义智能体的领域归属，支持层级结构。
    例如: {"primary": "钻井领域", "secondary": "地质分析"}
    """

    primary: str = Field(description="一级领域归属")
    secondary: Optional[str] = Field(None, description="二级领域归属，可选")
    tags: List[str] = Field(default_factory=list, description="其他相关的标签")
