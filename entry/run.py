import asyncio
from autogen_agentchat.ui import Console
from autogen_ext.models.ollama import OllamaChatCompletionClient
from autogen_ext.models.openai import OpenAIChatCompletionClient
from loguru import logger
from dotenv import load_dotenv

load_dotenv()
from typing import ClassVar, Union, cast, Dict, Any

from pydantic import BaseModel, ConfigDict, model_validator

from core.client import LLMFactory, ProviderType, DutyType
from core.assistant.factory import PMCAAgentFactory

from entry import PMCAEntryGraph, APPWorkbench


class PMCAMainProcessConfig(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    task: str = ""
    factory: PMCAAgentFactory | None = None
    app_workbench: APPWorkbench | None = None
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

        logger.info("正在初始化 PMCA 智能体工厂...")
        pmca_agents_factory = PMCAAgentFactory(
            model_client=cast(
                Union[OpenAIChatCompletionClient, OllamaChatCompletionClient],
                PMCAMainProcess.llm_config.model_client,
            ),
        )

        logger.success("PMCA 智能体工厂初始化成功...")

        cfg = cls.main_config

        cfg.app_workbench = APPWorkbench()

        cfg.registry_assistant_list = PMCAAgentFactory.list_registered_agents()

        cfg.function_assistant_list = PMCAAgentFactory.list_function_agents()

        cfg.factory = pmca_agents_factory

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
        load_dotenv()
        await cls.ensure_initialized()
        cfg = cls.main_config
        llm_cfg = cls.llm_config
        await PMCAEntryGraph.begin(cfg, llm_cfg)


if __name__ == "__main__":
    asyncio.run(PMCAMainProcess.go())
