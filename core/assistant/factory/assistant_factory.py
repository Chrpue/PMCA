from __future__ import annotations

from typing import TYPE_CHECKING, Any, Type, Dict, List, Optional
from autogen_agentchat.agents import AssistantAgent
from autogen_core.tools import BaseTool, Workbench
from autogen_ext.tools.mcp import McpWorkbench
from loguru import logger

from core.client.llm_factory import ProviderType
from .assistant_config import PMCAAssistantMetadata


from core.memory.factory.mem0 import PMCAMem0LocalService
from core.tools.factory import PMCAToolFactory


if TYPE_CHECKING:
    from core.team.core_assistants import PMCACoreAssistants
    from base.runtime import PMCATaskContext


class PMCAAssistantFactory:
    """
    现代化的、基于元数据蓝图的 AssistantAgent 工厂。
    """

    _registry: Dict[str, Type[PMCAAssistantMetadata]] = {}

    def __init__(self, ctx: "PMCATaskContext"):
        """
        工厂初始化，仅依赖于任务上下文。
        """
        from base.runtime import PMCATaskContext

        self.ctx = ctx

    @classmethod
    def register(cls, biz_type: str):
        def decorator(meta_cls: Type[PMCAAssistantMetadata]):
            cls._registry[biz_type] = meta_cls
            return meta_cls

        return decorator

    @classmethod
    def all_registered_assistants(cls) -> Dict[str, PMCAAssistantMetadata]:
        """
        获取所有已注册智能体的完整元数据对象信息
        """

        return {biz_type: meta() for biz_type, meta in cls._registry.items()}

    @classmethod
    def professional_assistants_description(cls) -> str:
        """
        为 Planner 获取特定智能体的“中文名”,“职能描述”,“元数据”字符串。
        """
        from core.team.core_assistants import PMCACoreAssistants

        all_assistants = cls.all_registered_assistants()
        desc_parts = [
            f"- {meta.chinese_name} ({name})\n{meta.duty}元数据:{meta.metadata}\n"
            for name, meta in all_assistants.items()
            if not PMCACoreAssistants.is_core_assistant(name)
        ]
        return "\n".join(desc_parts)

    def _create_tools(self, biz_type: str) -> Dict[str, Any]:
        """
        根据智能体的业务类型，为其创建 Workbench 或从 ToolFactory 获取 Tools。
        """
        meta_cls = self._registry[biz_type]
        meta = meta_cls()
        assistant_name = meta.name or biz_type

        if meta.tools_type == "workbench":
            if not meta.required_mcp_keys:
                logger.warning(
                    f"[{assistant_name}] tools_type=workbench 但未配置 required_mcp_keys"
                )
                return {}
            workbenches: List[Workbench] = []
            mcp_servers = self.ctx.task_env.get_mcp_servers()

            missing = []
            for key in meta.required_mcp_keys:
                params = mcp_servers.get(key)
                if params is None:
                    missing.append(key)
                    continue
                workbenches.append(McpWorkbench(server_params=mcp_servers[key]))
            if missing:
                logger.warning(f"[{assistant_name}] 缺失 MCP server keys: {missing}")
            return {"workbench": workbenches} if workbenches else {}

        elif meta.tools_type == "tools":
            tools: List[BaseTool] = PMCAToolFactory.tools(assistant_name)
            if tools:
                return {"tools": tools} if tools else {}
        return {}

    def create_assistant(
        self,
        biz_type: str,
        dynamic_hadoffs: Optional[List[str]] = None,
        **override_kwargs,
    ) -> AssistantAgent:
        """
        基于元数据构建一个 AssistantAgent 实例。
        """

        from .assistant_filter import PMCAAssistantFilter

        if biz_type not in self._registry:
            raise ValueError(f"未知的业务类型: {biz_type}")

        meta = self._registry[biz_type]()

        assistant_params = {
            "name": meta.name or biz_type,
            "model_client": self.ctx.llm_factory.client(meta.ability),
            "description": meta.description,
            "system_message": meta.system_message,
            "memory": [PMCAMem0LocalService.memory(meta.name or biz_type)],
            "model_client_stream": meta.model_client_stream,
            "reflect_on_tool_use": meta.reflect_on_tool_use,
            "max_tool_iterations": meta.max_tool_iterations,
            "tool_call_summary_format": meta.tool_call_summary_format,
            "handoffs": dynamic_hadoffs,
            "metadata": meta.metadata,
            # 注意: output_content_type 等更高级的参数也可以在这里添加
        }

        assistant_params = PMCAAssistantFilter(self).build_params(
            biz_type, assistant_params
        )
        assistant_params.update(self._create_tools(biz_type))
        assistant_params.update(override_kwargs)

        final_params = {k: v for k, v in assistant_params.items() if v is not None}

        return AssistantAgent(**final_params)
