import logging, os
import asyncio
from autogen_agentchat.agents import (
    MessageFilterAgent,
    MessageFilterConfig,
    PerSourceFilter,
)

from autogen_core.tools import StaticWorkbench, ToolSchema, ToolResult
from autogen_agentchat.teams import DiGraphBuilder, GraphFlow
from autogen_agentchat.ui import Console
from autogen_ext.models.ollama import OllamaChatCompletionClient
from autogen_ext.models.openai import OpenAIChatCompletionClient
from loguru import logger
from autogen_core.tools import Workbench
from dotenv import load_dotenv

load_dotenv()
from typing import ClassVar, Union, cast, Dict, Any, List

from pydantic import BaseModel, Field, ConfigDict, model_validator

from client import LLMFactory, ProviderType, DutyType
from base.agents.factory import PMCAAgentFactory
from base.memory import (
    PMCAAgentsGraphMemory,
)
from base.agents.special_agents import (
    PMCADecision,
    TeamDesicionResponse,
    AgentsDesicionResponse,
    CombinedDecisionResponse,
)

from base.agents.special_agents import PMCAUser
from base.team.factory import PMCATeamExecutor
from base.team import PMCASwarm
from entry import PMCAEntryGraph, APPWorkbench
# from base.knowledge.decision import (
#     PMCAAgentsDecisionKnowledge,
#     PMCATeamDecisionKnowledge,
# )


class PMCAMainProcessConfig(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    task: str = ""
    factory: PMCAAgentFactory | None = None
    app_workbench: APPWorkbench | None = None
    # team_decision_memory_workbench: Workbench | None = None
    # agents_decision_memory_workbench: Workbench | None = None
    registry_assistant_list: Dict[str, Dict[str, Any]] = {}
    function_assistant_list: Dict[str, Dict[str, Any]] = {}


class PMCALLMConfig(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    llm_provider: ProviderType = ProviderType.DEEPSEEK
    model_client: (
        Union[OpenAIChatCompletionClient, OllamaChatCompletionClient] | None
    ) = None
    llm_support_structured: bool | None = None

    @model_validator(mode="after")
    def _auto_fill(self):
        if self.model_client is None:
            self.model_client = LLMFactory.client(
                self.llm_provider,
                DutyType.BASE,
            )

        if self.llm_support_structured is None:
            self.llm_support_structured = self.llm_provider in (
                ProviderType.OPENAI,
                ProviderType.QWEN,
            )
        return self


class PMCAMainProcess:
    """MultiAgent Pipeline Runner"""

    main_config: ClassVar[PMCAMainProcessConfig] = PMCAMainProcessConfig()
    llm_config: ClassVar[PMCALLMConfig] = PMCALLMConfig()

    _initialized: ClassVar[bool] = False
    _init_lock: ClassVar[asyncio.Lock] = asyncio.Lock()

    @classmethod
    async def initialize_config(cls):
        """Initialize Config(just initialized onece)"""

        assert PMCAMainProcess.llm_config.model_client is not None, "模型调用出现异常……"

        pmca_agents_factory = PMCAAgentFactory(
            model_client=cast(
                Union[OpenAIChatCompletionClient, OllamaChatCompletionClient],
                PMCAMainProcess.llm_config.model_client,
            )
        )

        cfg = cls.main_config

        cfg.app_workbench = APPWorkbench()

        cfg.registry_assistant_list = PMCAAgentFactory.list_registered_agents()

        cfg.function_assistant_list = PMCAAgentFactory.list_function_agents()

        cfg.factory = pmca_agents_factory

        # cfg.team_decision_memory_workbench = (
        #     pmca_agents_factory.team_decision_memory_workbench()
        # )
        # cfg.agents_decision_memory_workbench = (
        #     pmca_agents_factory.agents_decision_memory_workbench()
        # )

    @classmethod
    async def ensure_initialized(cls) -> None:
        """Initialize Config(for outer)"""

        if cls._initialized:
            return
        async with cls._init_lock:
            if not cls._initialized:
                await cls.initialize_config()
                cls._initialized = True

    @classmethod
    async def go(cls) -> None:
        await cls.ensure_initialized()

        cfg = cls.main_config
        llm_cfg = cls.llm_config

        await PMCAEntryGraph.begin(cfg, llm_cfg)


if __name__ == "__main__":
    asyncio.run(PMCAMainProcess.go())
