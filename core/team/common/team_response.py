from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field


class PMCABizDecisionRequirements(BaseModel):
    """定义一个任务所需的团队能力画像，供 Planner 输出。"""

    primary_domain: str = Field(description="任务所需的主要领域")
    secondary_domain: Optional[str] = Field(None, description="任务所需的次要领域")
    required_tags: List[str] = Field(
        default_factory=list, description="任务必须具备的技能标签"
    )
    # 未来可扩展
    # exclude_assistants: List[str] = Field(default_factory=list, description="明确排除的智能体")
