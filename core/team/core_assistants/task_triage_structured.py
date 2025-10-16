from typing import Any, Dict, List, Literal, Optional

from core.assistant.factory import PMCAAssistantMetadata
from core.client import AbilityType
from .core_assistants import PMCACoreAssistants

from core.assistant.factory import PMCAAssistantFactory


@PMCAAssistantFactory.register(PMCACoreAssistants.TRIAGE_STRUCTURED.value)
class PMCATriageStructured(PMCAAssistantMetadata):
    """
    用户任务分诊结果的结构化输出
    """

    name: str = PMCACoreAssistants.TRIAGE_STRUCTURED.value

    description: str = "将分诊结果进行结构化输出的助手。"

    ability: AbilityType = AbilityType.DEFAULT

    tools_type: Literal["workbench", "tools", "none"] = "none"

    required_mcp_keys: List[str] = []
    tools: List[Any] = []

    model_client_stream: bool = False

    reflect_on_tool_use: bool = False

    max_tool_iterations: int = 10

    tool_call_summary_format: str = "{tool_name}: {arguments} -> {result}"

    metadata: Optional[Dict[str, str]] = {"domain": "system", "phase": "decision"}
