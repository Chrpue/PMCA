from typing import Any, Dict, List, Literal, Optional

from core.assistant.factory import PMCAAssistantMetadata
from core.client import AbilityType
from .core_assistants import PMCACoreAssistants

from core.assistant.factory import PMCAAssistantFactory


@PMCAAssistantFactory.register(PMCACoreAssistants.TRIAGE.value)
class PMCATriage(PMCAAssistantMetadata):
    """
    用户任务分诊（根据用户任务决策应由哪些智能体参加等）
    """

    name: str = PMCACoreAssistants.TRIAGE.value

    description: str = (
        "一个顶层的战略规划与任务抉择智能体，负责理解用户意图，对用户任务进行分诊。"
    )

    ability: AbilityType = AbilityType.DEFAULT

    tools_type: Literal["workbench", "tools", "none"] = "none"

    required_mcp_keys: List[str] = []
    tools: List[Any] = []

    model_client_stream: bool = True

    reflect_on_tool_use: bool = False

    max_tool_iterations: int = 10

    tool_call_summary_format: str = "{tool_name}: {arguments} -> {result}"

    metadata: Optional[Dict[str, str]] = {"domain": "system", "phase": "decision"}
