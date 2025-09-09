import asyncio
import uuid
import redis

from base.configs import EnvConfig
from core.client.llm_factory import LLMFactory, ProviderType
from core.assistant.factory import PMCAAgentFactory
from core.memory.factory.mem0 import PMCAMem0LocalService
from .system_workbench import (
    PMCATaskWorkbenchManager,
    PMCATaskContext,
)


class PMCARuntime:
    _instance = None
    _init_lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def initialize(self):
        async with self._init_lock:
            if getattr(self, "_initialized", False):
                return

            self.redis_client = redis.Redis(
                host=EnvConfig.REDIS_HOST,
                port=EnvConfig.REDIS_PORT,
                db=EnvConfig.REDIS_DB,
                password=EnvConfig.REDIS_PASSWORD,
                decode_responses=True,
            )
            self.redis_client.ping()

            provider = ProviderType(EnvConfig.LLM_PROVIDER.lower())
            self.llm_factory = LLMFactory()

            self.agent_factory = PMCAAgentFactory(
                provider=provider,
                llm_factory=self.llm_factory,
            )

            # 4. 加载或创建 agent 注册表并存入 Redis
            await self._initialize_agent_registry()

            # 5. 初始化 mem0
            await self._initialize_agent_memories()

            self._initialized = True

    async def _initialize_agent_registry(self):
        """
        从 AgentFactory 加载注册表。
        """
        self.registered_agents = PMCAAgentFactory.list_registered_agents()
        self.functional_agents = PMCAAgentFactory.list_functional_agents()

    async def _initialize_agent_memories(self):
        """
        为已注册的所有智能体初始化记忆实例
        """
        for agent_name in self.registered_agents.keys():
            PMCAMem0LocalService.memory(agent_name)

    def create_task_context(self):
        """创建一个用户级任务上下文，包含隔离的 workbench 与运行时资源引用。"""
        task_id = str(uuid.uuid4())[:8]
        workbench = PMCATaskWorkbenchManager.create_workbench(
            task_id, self.redis_client
        )
        return PMCATaskContext(
            task_id=task_id,
            task_mission=mission,
            task_model_provider="deepseek",
            task_model_name="deepseek-chat",
            task_workbench=workbench,
            agent_factory=self.agent_factory,
            llm_factory=self.llm_factory,
        )
