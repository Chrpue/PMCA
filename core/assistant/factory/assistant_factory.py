from __future__ import annotations

from typing import TYPE_CHECKING, Any, Type, Dict, List, Optional
from autogen_agentchat.agents import AssistantAgent
from autogen_core.tools import BaseTool, FunctionTool, Workbench
from autogen_ext.tools.mcp import McpWorkbench
from loguru import logger

from core.client.llm_factory import ProviderType
from .assistant_config import PMCAAssistantMetadata


from core.memory.factory.mem0 import PMCAMem0LocalService
from base.runtime import PMCATaskContext
from core.client import supports_structured_output
from base.prompts.task_triage import (
    PMCATRIAGE_SYSTEM_MESSAGE,
    PMCATRIAGE_REVIEWER_SYSTEM_MESSAGE,
    PMCATRIAGE_STRUCTURED_SYSTEM_MESSAGE,
)
from core.team.common import PMCATriageResult

if TYPE_CHECKING:
    from core.team.core_assistants import PMCACoreAssistants


class PMCAAssistantFactory:
    """
    现代化的、基于元数据蓝图的 AssistantAgent 工厂。
    """

    _registry: Dict[str, Type[PMCAAssistantMetadata]] = {}

    def __init__(self, ctx: PMCATaskContext):
        """
        工厂初始化，仅依赖于任务上下文。
        """
        self.ctx = ctx

    @classmethod
    def register(cls, biz_type: str):
        def decorator(meta_cls: Type[PMCAAssistantMetadata]):
            cls._registry[biz_type] = meta_cls
            return meta_cls

        return decorator

    def _create_triage_assistant_params(
        self, base_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        final_system_message = PMCATRIAGE_SYSTEM_MESSAGE.format(
            available_assistants=self.professional_assistants_description()
        )
        base_params["system_message"] = final_system_message

        return base_params

    def _create_triage_structured_assistant_params(
        self, base_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        final_system_message = PMCATRIAGE_STRUCTURED_SYSTEM_MESSAGE
        base_params["system_message"] = final_system_message

        return base_params

    def _create_triage_reviewer_assistant_params(
        self, base_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        final_system_message = PMCATRIAGE_REVIEWER_SYSTEM_MESSAGE.format(
            available_assistants=self.professional_assistants_description()
        )
        base_params["system_message"] = final_system_message

        # if supports_structured_output(ProviderType(provider), model_name):
        #     base_params["output_content_type"] = PMCATriageResult
        #     base_params["reflect_on_tool_use"] = False

        return base_params

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
            f"- {meta.chinese_name} ({name}):{meta.duty}:{meta.metadata}"
            for name, meta in all_assistants.items()
            if not PMCACoreAssistants.is_core_assistant(name)
        ]
        return "\n".join(desc_parts)

    def _create_workbench(
        self, meta: PMCAAssistantMetadata
    ) -> Optional[List[Workbench]]:
        """
        根据 required_mcp_keys 创建 Workbench 列表
        """

        if not meta.required_mcp_keys:
            return None

        workbenches: List[Workbench] = []
        mcp_servers = self.ctx.task_env.get_mcp_servers()
        for key in meta.required_mcp_keys:
            if key in mcp_servers:
                workbenches.append(McpWorkbench(server_params=mcp_servers[key]))
        return workbenches if workbenches else None

    def _create_tools(self, meta: PMCAAssistantMetadata) -> Optional[List[BaseTool]]:
        """
        将元数据中定义的函数转换为 autogen 的 FunctionTool 列表
        """

        if not meta.tools:
            return None

        autogen_tools: List[BaseTool] = []
        for tool in meta.tools:
            if callable(tool):
                description = (
                    tool.__doc__
                    if tool.__doc__
                    else f"一个名为 {tool.__name__} 的自定义工具。"
                )
                autogen_tools.append(FunctionTool(func=tool, description=description))
            elif isinstance(tool, BaseTool):
                autogen_tools.append(tool)
        return autogen_tools if autogen_tools else None

    def create_assistant(
        self,
        biz_type: str,
        dynamic_hadoffs: Optional[List[str]] = None,
        **override_kwargs,
    ) -> AssistantAgent:
        """
        基于元数据构建一个 AssistantAgent 实例。
        """
        if biz_type not in self._registry:
            raise ValueError(f"未知的业务类型: {biz_type}")

        meta = self._registry[biz_type]()

        model_client = self.ctx.llm_factory.client(meta.ability)

        # 2.2 工具或 Workbench (根据 tools_type 决定)
        tools: Optional[List[BaseTool]] = None
        workbench: Optional[List[Workbench]] = None
        if meta.tools_type == "tools":
            tools = self._create_tools(meta)
        elif meta.tools_type == "workbench":
            workbench = self._create_workbench(meta)

        memory = [PMCAMem0LocalService.memory(meta.name or biz_type)]

        assistant_params = {
            "name": meta.name or biz_type,
            "model_client": model_client,
            "description": meta.description,
            "system_message": meta.system_message,
            "memory": memory,
            "tools": tools,
            "workbench": workbench,
            "model_client_stream": meta.model_client_stream,
            "reflect_on_tool_use": meta.reflect_on_tool_use,
            "max_tool_iterations": meta.max_tool_iterations,
            "tool_call_summary_format": meta.tool_call_summary_format,
            "handoffs": dynamic_hadoffs,
            "metadata": meta.metadata,
            # 注意: output_content_type 等更高级的参数也可以在这里添加
        }

        from core.team.core_assistants import PMCACoreAssistants

        if biz_type == PMCACoreAssistants.TRIAGE.value:
            assistant_params = self._create_triage_assistant_params(assistant_params)

        if biz_type == PMCACoreAssistants.TRIAGE_REVIEWER.value:
            assistant_params = self._create_triage_reviewer_assistant_params(
                assistant_params
            )

        if biz_type == PMCACoreAssistants.TRIAGE_STRUCTURED.value:
            assistant_params = self._create_triage_structured_assistant_params(
                assistant_params
            )

        assistant_params.update(override_kwargs)

        final_params = {k: v for k, v in assistant_params.items() if v is not None}

        return AssistantAgent(**final_params)


# if meta.tools_type == "tools":
#     tools = ToolFactory().get_tools_for_agent(agent_name=meta.name or biz_type)
#     workbench = None
# elif meta.tools_type == "mcp":
#     tools = None
#     workbench = ...  # 原有逻辑
