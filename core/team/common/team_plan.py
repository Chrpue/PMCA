from typing import List, Literal, Optional, Dict, Any
from pydantic import BaseModel, Field

# 定义Orchestrator可以调度的执行团队的类型
ExecutorType = Literal[
    "DataAnalysisSwarm", "DrillingSwarm", "MagenticOneTeam", "PMCAUserProxy"
]


class PlanStep(BaseModel):
    """定义执行计划中的单个步骤。"""

    step_index: int = Field(description="任务步骤的序号，从1开始。")
    description: str = Field(description="对这个步骤需要完成的目标的清晰、简洁的描述。")
    executor: ExecutorType = Field(description="指定负责执行此步骤的团队或智能体。")
    params: Dict[str, Any] = Field(
        default_factory=dict, description="执行此步骤所需的具体参数或输入数据。"
    )
    status: Literal["pending", "in_progress", "completed", "failed"] = Field(
        "pending", description="当前步骤的执行状态。"
    )


class ExecutionPlan(BaseModel):
    """定义完整的、多步骤的执行计划。"""

    plan: List[PlanStep] = Field(description="包含所有任务步骤的列表。")
    current_step: int = Field(1, description="当前正在执行或即将执行的步骤序号。")
    original_mission: str = Field(description="用户最初的完整任务描述。")

    def get_next_step(self) -> Optional[PlanStep]:
        """获取下一个待执行的步骤。"""
        if self.current_step > len(self.plan):
            return None
        return self.plan[self.current_step - 1]
