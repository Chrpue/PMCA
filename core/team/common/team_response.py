from typing import List, Literal, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class TeamGroup(BaseModel):
    """
    定义一个复杂任务中的智能体分组。
    """

    name: str = Field(
        ...,
        description="分组的名称，必须以 'PMCA-Swarm-' 为前缀。",
        examples=["PMCA-Swarm-DataAnalysis", "PMCA-Swarm-DrillGeologyAnalysis"],
    )
    description: str = Field(
        ..., max_length=100, description="对该分组能力的简要描述，不超过50个汉字。"
    )
    participants: List[str] = Field(
        ...,
        description="参与此分组的智能体英文名列表。",
        examples=[["PMCADataExplorer", "PMCAChartGenerator"]],
    )

    @field_validator("name")
    @classmethod
    def validate_name_prefix(cls, v: str) -> str:
        """验证分组名称是否以 'PMCA-Swarm-' 开头。"""
        if not v.startswith("PMCA-Swarm-"):
            raise ValueError("分组名称必须以 'PMCA-Swarm-' 为前缀")
        return v


class PMCATriageResult(BaseModel):
    """
    任务分诊决策的结构化输出模型。
    该模型完整地映射了分诊员的所有决策字段，并包含了确保逻辑一致性的验证规则。
    """

    is_clear: bool = Field(..., description="任务描述是否清晰，足以支撑任务顺利进行。")
    comment: str = Field(
        ...,
        description="对任务清晰度的评论。如果不清晰，指出问题；如果清晰，则返回固定欢迎语。",
    )
    task_type: Literal["simple", "complex"] = Field(
        ..., description="任务的类型，必须是 'simple' 或 'complex' 之一。"
    )
    person: Optional[str] = Field(
        default=None,
        description="如果任务类型为 'simple'，则指定负责执行的单个智能体名称；否则为空。",
    )
    team: Optional[List[TeamGroup]] = Field(
        default=None,
        description="如果任务类型为 'complex'，则返回智能体分组列表；否则为空。",
    )
    enable_advanced: bool = Field(
        ...,
        description="任务执行是否需要高级功能（如代码生成、网页浏览、本地文件检索）的支持。",
    )

    @model_validator(mode="after")
    def check_mutual_exclusion_and_conditions(self) -> "PMCATriageResult":
        """
        执行核心的业务逻辑校验：
        1.  校验任务清晰度与评论之间的关系。
        2.  校验简单任务与复杂任务字段的互斥性。
        """
        # 规则1: 任务描述不清晰时，必须给出具体评论
        if not self.is_clear:
            if self.comment == "我们将尽力完成您的需求":
                raise ValueError(
                    "当 is_clear 为 False 时，comment 字段必须说明任务不清晰的具体原因。"
                )
        else:
            # 如果任务清晰，person 或 team 必须至少有一个被指定（根据任务类型）
            if self.task_type == "simple" and self.person is None:
                raise ValueError("清晰的简单任务必须指定 'person'。")
            # 注意：复杂任务的 team 可以是空列表 []
            if self.task_type == "complex" and self.team is None:
                raise ValueError("清晰的复杂任务必须提供 'team' 字段（可以为空列表）。")

        # 规则2: 简单任务与复杂任务的互斥原则
        if self.task_type == "simple":
            if self.person is None:
                raise ValueError(
                    "当 task_type 为 'simple' 时，'person' 字段必须被指定。"
                )
            if self.team is not None:
                raise ValueError(
                    "当 task_type 为 'simple' 时，'team' 字段必须为空 (None)。"
                )

        elif self.task_type == "complex":
            if self.team is None:
                raise ValueError(
                    "当 task_type 为 'complex' 时，'team' 字段必须被提供（即使是空列表）。"
                )
            if self.person is not None:
                raise ValueError(
                    "当 task_type 为 'complex' 时，'person' 字段必须为空 (None)。"
                )

        return self
