from typing import Optional, List
from autogen_agentchat.agents import AssistantAgent
from typing import Type, Dict, Any

from .factory_config import PMCAFactoryConfig
from .agent_metadata import PMCAAgentMetadata
from autogen_ext.tools.mcp import McpWorkbench

from core.memory.factory.mem0 import PMCAMem0LocalService
from core.client import LLMFactory, ProviderType, AbilityType

from loguru import logger


PMCASpecialAgents = [
    "PMCACodeGenExec",
]

PMCAExcludeAgents = [
    "PMCATeamDecision",
    "PMCAAgentsDecision",
    "PMCATeamDecisionCritic",
    "PMCAAgentsDecisionCritic",
    "PMCADecisionReviewer",
    "PMCASwarmPlanner",
    "PMCAGraphFinished",
]


class PMCAAssistantFactory(PMCAFactoryConfig):
    """AssistantAgent Factory"""

    _registry: Dict[str, Type[PMCAAgentMetadata]] = {}

    def __init__(self, provider: ProviderType, llm_factory: LLMFactory):
        super().__init__()
        self._provider = provider
        self._llm_factory = llm_factory

    @property
    def registry(cls):
        return cls._registry

    @classmethod
    def register(cls, biz_type: str):
        def decorator(meta_cls: Type[PMCAAgentMetadata]):
            cls._registry[biz_type] = meta_cls
            return meta_cls

        return decorator

    @classmethod
    def list_registered_agents(cls) -> Dict[str, Dict[str, Any]]:
        """obtain all registered agents"""
        return {
            biz_type: {
                "chinese_name": meta_cls.chinese_name,
                "description": meta_cls.description,
                "duty": meta_cls.duty,
                "avaliable_tools": meta_cls.required_mcp_keys,
                "model_type": meta_cls.model_duty_type,
            }
            for biz_type, meta_cls in cls._registry.items()
        }

    @classmethod
    def list_functional_agents(cls):
        """obtain all function agents except team decision agents"""
        return {
            key: value
            for key, value in PMCAAssistantFactory.list_registered_agents().items()
            if key not in PMCAExcludeAgents
        }

    @classmethod
    def list_partners_desc(cls, participants: List[str]):
        """obtain partners description"""

        partners_desc = "\n".join(
            [
                f"- {info.get('chinese_name', '')}: {info.get('duty', '')}"
                for partner, info in PMCAAssistantFactory.list_functional_agents().items()
                if partner in participants
            ]
        )

        return partners_desc

    # def team_decision_memory_workbench(self):
    #     filtered_mcp_params = [
    #         value
    #         for key, value in self._mcp_server_dict.items()
    #         if key == "MCP_SERVER_LIGHTRAG_APP"
    #     ]
    #     return McpWorkbench(filtered_mcp_params[-1])
    #
    # def agents_decision_memory_workbench(self):
    #     filtered_mcp_params = [
    #         value
    #         for key, value in self._mcp_server_dict.items()
    #         if key == "MCP_SERVER_LIGHTRAG_APP"
    #     ]
    #     return McpWorkbench(filtered_mcp_params[-1])

    def _filtered_workbench(self, biz_type):
        """Responsible for filtering the workbench according to the MCP list defined by the agent"""

        meta = self._registry[biz_type]()
        if meta.required_mcp_keys:
            filtered_mcp_params = [
                value
                for key, value in self._mcp_server_dict.items()
                if key in meta.required_mcp_keys
            ]
        else:
            filtered_mcp_params = []

        workbenches = []
        if filtered_mcp_params:
            for mcp_params in filtered_mcp_params:
                workbenches.append(McpWorkbench(server_params=mcp_params))
        return workbenches

    def create_agent(self, biz_type: str, **kwargs) -> AssistantAgent:
        if biz_type not in self._registry:
            raise ValueError(f"未知的业务类型: {biz_type}")

        meta = self._registry[biz_type]()

        model_ability = getattr(meta, "ability", AbilityType.DEFAULT)

        model_client = self._llm_factory.client(AbilityType(model_ability))

        mcp_workbench = self._filtered_workbench(biz_type) or None

        memory = PMCAMem0LocalService.memory(meta.name or biz_type)

        agent_args = {
            "name": meta.name or biz_type,
            "model_client": model_client,
            "system_message": meta.system_message,
            "description": meta.description,
            "model_client_stream": self.model_client_stream,
            "tool_call_summary_format": self.tool_call_summary_format,
            "workbench": mcp_workbench,
            "memory": [memory],
            **kwargs,
        }

        agent_args["workbench"] = self._filtered_workbench(biz_type) or None

        agent = AssistantAgent(**agent_args)

        return agent
