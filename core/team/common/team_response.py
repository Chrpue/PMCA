from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field


class PMCATriageResult(BaseModel):
    """
    定义任务分诊阶段的输出结果。
    """

    task_type: Literal["simple_task", "complex_task", "clarification_needed"] = Field(
        description="任务的分类结果。"
    )
    comment: Optional[str] = Field(
        None,
        description="如果任务需要澄清，这里是需要向用户提出的问题；如果是简单任务，这里是最终答案。",
    )
    required_executors: Optional[List[str]] = Field(
        None, description="如果任务复杂，这里是经过分析后，推荐参与任务的执行单元列表。"
    )


class PMCABizDecisionRequirements(BaseModel):
    """定义一个任务所需的团队能力画像，供 Planner 输出。"""

    primary_domain: str = Field(description="任务所需的主要领域")
    secondary_domain: Optional[str] = Field(None, description="任务所需的次要领域")
    required_tags: List[str] = Field(
        default_factory=list, description="任务必须具备的技能标签"
    )
    # 未来可扩展
    # exclude_assistants: List[str] = Field(default_factory=list, description="明确排除的智能体")
