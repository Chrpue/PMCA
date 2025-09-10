import asyncio
import uuid
from loguru import logger
from redis import asyncio as aioredis

from base.configs import PMCASystemEnvConfig
from core.client.llm_factory import LLMFactory, ProviderType
from core.assistant.factory import PMCAAgentFactory
from core.memory.factory.mem0 import PMCAMem0LocalService

from .system_workbench import (
    PMCATaskWorkbenchManager,
    PMCATaskContext,
)


class PMCARuntime:
    """应用级单例：只初始化一次 LLM 工厂、Agent 工厂、Redis 连接、注册表与 mem0。"""

    _instance = None
    _init_lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def initialize(self) -> None:
        async with self._init_lock:
            if getattr(self, "_initialized", False):
                return

            # 1) 连接 Redis（异步）
            self.redis = aioredis.Redis(
                host=PMCASystemEnvConfig.REDIS_HOST,
                port=PMCASystemEnvConfig.REDIS_PORT,
                db=PMCASystemEnvConfig.REDIS_DB,
                password=PMCASystemEnvConfig.REDIS_PASSWORD,
                decode_responses=True,
            )
            await self.redis.ping()
            logger.success("Redis connected.")

            # 2) LLM 工厂 / Provider
            #   - 优先使用 DEFAULT_PROVIDER（如果没有就回退到 LLM_TYPE）
            provider_str = (
                getattr(PMCASystemEnvConfig, "DEFAULT_PROVIDER", None)
                or PMCASystemEnvConfig.LLM_TYPE
            )
            self.provider = ProviderType(provider_str.lower())
            self.llm_factory = LLMFactory()

            # 3) Agent 工厂
            self.agent_factory = PMCAAgentFactory(
                provider=self.provider,
                llm_factory=self.llm_factory,
            )

            # 4) 载入注册表
            await self._initialize_agent_registry()

            # 5) 初始化各 Agent 的 mem0
            await self._initialize_agent_memories()

            self._initialized = True
            logger.success("PMCARuntime initialized.")

    async def _initialize_agent_registry(self) -> None:
        """读取 AgentFactory 注册表并缓存。"""
        self.registered_agents = PMCAAgentFactory.list_registered_agents()
        self.functional_agents = PMCAAgentFactory.list_functional_agents()
        logger.info(f"Registered agents: {list(self.registered_agents.keys())}")

    async def _initialize_agent_memories(self) -> None:
        """为每个已注册智能体初始化 mem0。"""
        for agent_name in self.registered_agents.keys():
            PMCAMem0LocalService.memory(agent_name)

    def create_task_context(self, mission: str = "") -> PMCATaskContext:
        """创建任务上下文（任务隔离）。"""
        task_id = uuid.uuid4().hex[:8]
        workbench = PMCATaskWorkbenchManager.create_workbench(task_id, self.redis)
        return PMCATaskContext(
            task_id=task_id,
            task_mission=mission,
            task_workbench=workbench,
            agent_factory=self.agent_factory,
            llm_factory=self.llm_factory,
        )
