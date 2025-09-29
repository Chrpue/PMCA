from typing import List, Literal, Union
from pydantic import BaseModel, Field


class PMCAComplexTaskTeamGroup(BaseModel):
    name: str = Field(
        ...,
        description="分组名称，必须以 'PMCA-Swarm-' 为前缀",
        pattern=r"^PMCA-Swarm-.*$",
    )
    description: str = Field(
        ..., description="该分组主要做什么工作（50字以内）", max_length=50
    )
    participants: List[str] = Field(
        ..., description="参与该分组的智能体英文名列表 (例如 ['PMCAAssistant'])"
    )


class PMCASimpleTaskResponse(BaseModel):
    task_type: Literal["simple"]
    assistant: str = Field(..., description="执行简单任务的智能体英文名称")


class PMCAComplexTaskResponse(BaseModel):
    task_type: Literal["complex"]
    team: List[PMCAComplexTaskTeamGroup] = Field(
        ..., description="执行复杂任务的智能体分组列表"
    )
    enable_advanced: bool = Field(
        ..., description="任务执行是否需要高级功能（代码、网页、文件）的支持"
    )


class PMCATriageResult(BaseModel):
    result: Union[PMCASimpleTaskResponse, PMCAComplexTaskResponse] = Field(
        ...,
        discriminator="task_type",
        description="根据任务类型 `simple` 或 `complex` 启用相应的结构。",
    )
