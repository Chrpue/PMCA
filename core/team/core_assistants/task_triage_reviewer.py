from typing import Any, Dict, List, Literal, Optional

from core.assistant.factory import PMCAAssistantMetadata
from core.client import AbilityType
from .core_assistants import PMCACoreAssistants

from core.assistant.factory import PMCAAssistantFactory


@PMCAAssistantFactory.register(PMCACoreAssistants.TRIAGE_REVIEWER.value)
class PMCATriageReviewer(PMCAAssistantMetadata):
    """
    用户任务分诊评测智能体（对任务分诊智能体产出的结果进行评估的智能体）
    """

    name: str = PMCACoreAssistants.TRIAGE_REVIEWER.value

    description: str = "一个评估针对用户任务意图理解、行动分工的决策结果的智能体，负责评估任务分诊是否合理，提出建设性意见。"

    ability: AbilityType = AbilityType.DEFAULT

    tools_type: Literal["workbench", "tools", "none"] = "workbench"

    required_mcp_keys: List[str] = []
    tools: List[Any] = []

    model_client_stream: bool = True

    reflect_on_tool_use: bool = False

    max_tool_iterations: int = 10

    tool_call_summary_format: str = "{tool_name}: {arguments} -> {result}"

    metadata: Optional[Dict[str, str]] = {"domain": "system", "phase": "critic"}
