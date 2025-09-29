from __future__ import annotations
from typing import List, Dict
from autogen_core.tools import BaseTool, FunctionTool

from .tool_registry import PMCAToolRegistry


class PMCAToolFactory:
    """聚合 Provider → 返回某智能体的全部工具（去重）。"""

    @staticmethod
    def tools(assistant_name: str) -> List[BaseTool]:
        registry = PMCAToolRegistry()
        tools: List[FunctionTool] = []
        for provider in registry.providers(assistant_name):
            tools.extend(provider.for_assistant(assistant_name))
        dedup: Dict[str, FunctionTool] = {t.name: t for t in tools}
        return list(dedup.values())
