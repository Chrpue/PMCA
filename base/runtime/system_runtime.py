import asyncio
from typing import TYPE_CHECKING
import uuid
from loguru import logger
from redis import asyncio as aioredis

from base.configs import PMCASystemEnvConfig
from core.client.llm_factory import LLMFactory

if TYPE_CHECKING:
    from core.assistant.factory import PMCAAssistantFactory
    from base.runtime import PMCATaskContext
from core.memory.factory.mem0 import PMCAMem0LocalService

from .task_context import PMCATaskContext
from .system_workbench import PMCATaskWorkbenchManager
import core.assistant.built_in


class PMCARuntime:
    """应用级单例：只初始化一次 LLM 工厂、Agent 工厂、Redis 连接、注册表与 mem0。"""

    _instance = None
    _init_lock = asyncio.Lock()

    redis: aioredis.Redis
    llm_factory: LLMFactory

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

            self.llm_factory = LLMFactory()

            await self._initialize_assistants_registry()

            await self._initialize_assistants_memories()

            self._initialized = True
            logger.success("PMCARuntime initialized.")

    def _log_registered_assistants(self):
        """打印日志，验证所有智能体是否已成功注册。"""
        from core.assistant.factory import PMCAAssistantFactory

        registered_agents = PMCAAssistantFactory.all_registered_assistants().keys()
        logger.info(f"当前已注册的智能体: {list(registered_agents)}")

    async def _initialize_assistants_registry(self) -> None:
        """读取 AgentFactory 注册表并缓存。"""
        from core.assistant.factory import PMCAAssistantFactory

        self._registered_assistants = PMCAAssistantFactory.all_registered_assistants()
        logger.info(f"Registered agents: {list(self._registered_assistants.keys())}")

    async def _initialize_assistants_memories(self) -> None:
        """为每个已注册智能体初始化 mem0。"""
        for agent_name in self._registered_assistants.keys():
            PMCAMem0LocalService.memory(agent_name)

    def create_task_context(self, mission: str = "") -> PMCATaskContext:
        """创建任务上下文（任务隔离）。"""
        from core.assistant.factory import PMCAAssistantFactory

        task_id = uuid.uuid4().hex[:8]
        workbench = PMCATaskWorkbenchManager.create_workbench(task_id, self.redis)
        task_ctx = PMCATaskContext(
            task_id=task_id,
            task_mission=mission,
            task_env=PMCASystemEnvConfig,
            task_workbench=workbench,
            llm_factory=self.llm_factory,
        )

        assistant_factory = PMCAAssistantFactory(ctx=task_ctx)
        task_ctx.assistant_factory = assistant_factory
        logger.success(f"Task context [{task_id}] created successfully.")

        return task_ctx
