from typing import Any, Dict, List, Literal, Optional

from core.client import AbilityType
from core.team.common.team_messages import PMCARoutingMessages
from .core_assistants import PMCACoreAssistants

from core.assistant.factory import PMCAAssistantFactory, PMCAAssistantMetadata


@PMCAAssistantFactory.register(PMCACoreAssistants.ORCHESTRATOR.value)
class PMCAOrchestrator(PMCAAssistantMetadata):
    """
    顶层战略规划师，负责任务分解和执行单元的调度。
    """

    name: str = PMCACoreAssistants.ORCHESTRATOR.value

    description: str = "一个顶层的战略规划与任务协调智能体，负责理解用户意图，制定执行计划，并协调其他成员完成任务。"

    system_message: str = """
"""
    ability: AbilityType = AbilityType.DEFAULT

    tools_type: Literal["workbench", "tools", "none"] = "workbench"

    required_mcp_keys: List[str] = [
        "MCP_SERVER_SEQUENTIALTHINKING",
        "MCP_SERVER_TODO",
    ]

    tools: List[Any] = []

    model_client_stream: bool = True

    reflect_on_tool_use: bool = True

    max_tool_iterations: int = 10

    tool_call_summary_format: str = "{tool_name}: {arguments} -> {result}"

    metadata: Optional[Dict[str, str]] = None
