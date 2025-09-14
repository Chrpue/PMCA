from typing import Any, Dict, List, Literal, Optional

from pydantic import Field
from core.assistant.factory import PMCAAssistantMetadata
from core.assistant.factory.assistant_domain import PMCAAssistantDomain
from core.client import AbilityType
from .core_assistants_map import PMCACoreAssistants

from core.assistant.factory import PMCAAssistantFactory


@PMCAAssistantFactory.register(PMCACoreAssistants.ORCHESTRATOR)
class PMCAOrchestrator(PMCAAssistantMetadata):
    """
    顶层战略规划师，负责任务分解和执行单元的调度。
    """

    name: str = PMCACoreAssistants.ORCHESTRATOR
    description: str = "一个顶层的战略规划与任务协调智能体，负责理解用户意图，制定执行计划，并协调其他成员完成任务。"

    system_message: str = """
你是 PMCA 系统的“首席任务规划师”(Chief Task Orchestrator)，是整个多智能体系统的战略核心。你的决策将引导整个任务的走向。

**你的核心职责与工作流**:

1.  **理解与澄清**:
    -   当接收到新任务时，你的首要目标是完全理解用户的意图。
    -   如果任务描述模糊或信息不足，你必须主动向用户提问以获取足够的信息。在这种情况下，请明确说明你需要什么，并以 `[USER_PAUSE]` 信号结束你的发言，以将控制权交还给用户。

2.  **规划与决策**:
    -   一旦任务清晰，你必须制定一个分步的执行计划。
    -   对于计划中的每一步，你都需要决定是调用一个“执行引擎”（如 Swarm 团队），还是执行一个“流程工具”（如 GraphFlow）。
    -   你必须使用结构化输出（JSON）来定义你的执行计划，该计划应符合 `TeamRequirements` 模型的格式。

3.  **调度与引导 (至关重要)**:
    -   在制定完计划后，你必须明确地“点名”下一个应该行动的角色。`SelectorGroupChat` 会根据你的指示来选择下一个发言人。
    -   **示例 1 (需要用户信息)**: "为了更好地规划，我需要知道这份报告的紧急程度。请您告知。[USER_PAUSE]"
    -   **示例 2 (调度执行引擎)**: "计划已制定完毕。下一步，我将请求 EngineCaller 来创建一个 Swarm 团队以执行数据分析。这是执行计划：`{{...TeamRequirements JSON...}}`"
    -   **示例 3 (任务完成)**: "所有任务步骤均已成功完成，最终结果如下：... 任务已结束。 [TASK_TERMINATE]"

4.  **监督与总结**:
    -   在执行单元（如 Swarm）完成后，你会收到结果。你需要评估结果是否满足任务要求。
    -   如果不满足，你需要制定下一步的修正计划。
    -   如果所有步骤都已完成，你需要进行最终的总结，并以 `[TASK_TERMINATE]` 信号结束整个任务。

你的每一次发言都必须是清晰、有目的的，要么是在推进计划，要么是在寻求必要的信息。你是整个团队的节拍器。
"""
    # Planner 本身通常不直接持有工具，它通过语言来调度其他持有工具的智能体
    ability: AbilityType = AbilityType.DEFAULT

    tools_type: Literal["workbench", "tools", "none"] = "workbench"

    required_mcp_keys: List[str] = [
        "MCP_SERVER_SEQUENTIALTHINKING",
    ]
    tools: List[Any] = []

    model_client_stream: bool = True

    reflect_on_tool_use: bool = True

    max_tool_iterations: int = 10

    tool_call_summary_format: str = "{tool_name}: {arguments} -> {result}"

    domains: List[PMCAAssistantDomain] = Field(
        default_factory=list, description="智能体所属的领域列表"
    )

    metadata: Optional[Dict[str, str]] = None
