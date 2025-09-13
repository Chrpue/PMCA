# core/assistant/factory/agent_factory.py (最终版)

from typing import Type, Dict, Any, List, Optional
from autogen_agentchat.agents import AssistantAgent
from autogen_core.tools import BaseTool, FunctionTool, Workbench
from autogen_ext.tools.mcp import McpWorkbench

from .assistant_config import PMCAAssistantMetadata
from core.memory.factory.mem0 import PMCAMem0LocalService
from core.team.common import PMCABizDecisionRequirements
from base.runtime import PMCATaskContext


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

    @classmethod
    def get_all_registered_assistants(cls) -> Dict[str, PMCAAssistantMetadata]:
        """
        获取所有已注册智能体的完整元数据对象信息
        """

        return {biz_type: meta() for biz_type, meta in cls._registry.items()}

    @classmethod
    def filter_assistants_by_requirements(
        cls, requirements: PMCABizDecisionRequirements
    ) -> Dict[str, PMCAAssistantMetadata]:
        """
        根据 Planner 输出的 PMCABizDecisionRequirements 结构体，智能筛选出候选智能体。
        """
        all_assistants = cls.get_all_registered_assistants()
        candidates = {}
        for name, meta in all_assistants.items():
            for domain in meta.domains:
                if domain.primary != requirements.primary_domain:
                    continue
                if (
                    requirements.secondary_domain
                    and domain.secondary != requirements.secondary_domain
                ):
                    continue
                if all(tag in domain.tags for tag in requirements.required_tags):
                    candidates[name] = meta
                    break
        return candidates

    @classmethod
    def get_agents_description_for_planner(
        cls, assistants: Dict[str, PMCAAssistantMetadata]
    ) -> str:
        """
        为 Planner 获取特定智能体的“中文名”和“职能描述”字符串。
        """
        desc_parts = []
        for name, meta in assistants.items():
            desc_parts.append(f"- {meta.chinese_name} ({name}): {meta.duty}")
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

        # 1. 获取元数据蓝图实例
        meta = self._registry[biz_type]()

        # 2. 准备所有构造参数

        # 2.1 模型客户端 (根据 ability 决定)
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

        assistant_params.update(override_kwargs)

        final_params = {k: v for k, v in assistant_params.items() if v is not None}

        return AssistantAgent(**final_params)
