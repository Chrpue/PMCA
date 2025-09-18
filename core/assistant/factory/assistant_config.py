from typing import List, Optional, Dict, Any, Literal
from core.client import AbilityType


class PMCAAssistantMetadata:
    """
    一个声明式的、完全可配置的智能体元数据蓝图。
    它包含了 AssistantAgent 的所有可配置参数，并提供了合理的默认值。
    每个具体的智能体定义都应继承此类并按需覆盖。
    """

    # ------------------------------------------------------------------
    # --- 核心身份与提示词  ---
    # ------------------------------------------------------------------
    name: Optional[str] = None
    description: str = "一个 PMCA 智能体。"
    system_message: str = "你是一个有用的助手。"
    chinese_name: str = ""
    duty: str = ""

    # ------------------------------------------------------------------
    # --- 模型与能力选择  ---
    # ------------------------------------------------------------------
    ability: AbilityType = AbilityType.DEFAULT

    # ------------------------------------------------------------------
    # --- 工具与 Workbench 控制  ---
    # ------------------------------------------------------------------
    tools_type: Literal["workbench", "tools", "none"] = "workbench"
    required_mcp_keys: List[str] = []  # 当 tools_type='workbench' 时使用
    tools: List[Any] = []  # 当 tools_type='tools' 时使用

    # ------------------------------------------------------------------
    # --- AssistantAgent 完整参数映射 (提供默认值，可被覆盖) ---
    # ------------------------------------------------------------------
    handoffs: Optional[List[str]] = None

    model_client_stream: bool = False

    reflect_on_tool_use: bool = True

    max_tool_iterations: int = 10

    tool_call_summary_format: str = "{tool_name}: {arguments} -> {result}"

    metadata: Optional[Dict[str, str]] = {"domain": "base"}
