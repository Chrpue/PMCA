import asyncio
import json
import redis
from typing import Dict, Any, Union, cast
from loguru import logger

from autogen_ext.models.ollama import OllamaChatCompletionClient
from autogen_ext.models.openai import OpenAIChatCompletionClient

from core.assistant.factory import PMCAAgentFactory
from core.memory.factory.mem0 import PMCAMem0LocalService
from core.client import LLMFactory, ProviderType, DutyType
from base.configs import PMCAEnvConfig
from utils import PMCATitle


class PMCASystemRuntime:
    """
    应用核心运行时，采用单例模式。
    负责在应用启动时初始化所有核心组件，并利用 Redis 实现智能体注册表的持久化。
    """

    _instance = None
    _init_lock = asyncio.Lock()

    # --- 核心组件 ---
    agent_factory: PMCAAgentFactory
    llm_client: Union[OpenAIChatCompletionClient, OllamaChatCompletionClient]
    llm_support_structured: bool
    registered_agents: Dict[str, Dict[str, Any]]
    functional_agents: Dict[str, Dict[str, Any]]
    redis_client: redis.Redis

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PMCASystemRuntime, cls).__new__(cls)
        return cls._instance

    async def initialize(self):
        """
        初始化所有核心组件。这个方法是幂等的，只会执行一次。
        """
        async with self._init_lock:
            if hasattr(self, "_initialized") and self._initialized:
                return

            PMCATitle("PMCA Application Runtime Initializing")

            # 1. 初始化 Redis 连接
            try:
                logger.info(
                    f"正在连接到 Redis ({PMCAEnvConfig.REDIS_HOST}:{PMCAEnvConfig.REDIS_PORT})..."
                )
                self.redis_client = redis.Redis(
                    host=PMCAEnvConfig.REDIS_HOST,
                    port=PMCAEnvConfig.REDIS_PORT,
                    db=PMCAEnvConfig.REDIS_DB,
                    password=PMCAEnvConfig.REDIS_PASSWORD,
                    decode_responses=True,  # 自动解码
                )
                self.redis_client.ping()
                logger.success("Redis 连接成功.")
            except redis.exceptions.ConnectionError as e:
                logger.error(f"无法连接到 Redis: {e}")
                logger.error("请确保 Redis 服务正在运行，并且 .env 中的配置正确。")
                exit(1)

            # 2. 初始化 LLM Client
            logger.info(
                f"正在初始化 LLM Client (Provider: {PMCAEnvConfig.LLM_TYPE})..."
            )
            self.llm_client = LLMFactory.client(
                ProviderType(PMCAEnvConfig.LLM_TYPE.lower()), DutyType.BASE
            )
            self.llm_support_structured = PMCAEnvConfig.LLM_TYPE.lower() in (
                "openai",
                "qwen",
            )
            logger.success("LLM Client 初始化成功.")

            # 3. 初始化 Agent Factory
            self.agent_factory = PMCAAgentFactory(model_client=self.llm_client)
            logger.success("Agent Factory 初始化成功.")

            # 4. 加载或创建智能体注册表
            await self._load_or_create_agent_registry()

            # 5. (可选) 初始化其他服务，例如每个智能体的记忆
            await self._initialize_agent_memories()

            self._initialized = True
            PMCATitle("PMCA Application Runtime Initialized Successfully")

    async def _load_or_create_agent_registry(self):
        """
        尝试从 Redis 加载智能体注册表，如果失败则动态创建并存入 Redis。
        """
        logger.info("正在加载智能体注册表...")
        try:
            cached_registry_json = self.redis_client.get(
                PMCAEnvConfig.REDIS_AGENT_REGISTRY_KEY
            )
            if cached_registry_json:
                logger.info("从 Redis 缓存中发现注册表。")
                cached_registry = json.loads(cached_registry_json)
                self.registered_agents = cached_registry["registered_agents"]
                self.functional_agents = cached_registry["functional_agents"]
                # 关键: 将加载的注册表同步回 Agent Factory 的类变量中
                PMCAAgentFactory._registry = {
                    name: type(
                        name,
                        (object,),
                        {
                            "chinese_name": info.get("chinese_name"),
                            "description": info.get("description"),
                            "duty": info.get("duty"),
                            "required_mcp_keys": info.get("avaliable_tools", []),
                        },
                    )
                    for name, info in self.registered_agents.items()
                }

            else:
                logger.warning("Redis 缓存未命中。现在动态扫描并创建注册表...")
                # 动态扫描在导入时已经通过装饰器 @PMCAAgentFactory.register 完成
                self.registered_agents = PMCAAgentFactory.list_registered_agents()
                self.functional_agents = PMCAAgentFactory.list_function_agents()

                # 将新创建的注册表存入 Redis
                registry_to_cache = {
                    "registered_agents": self.registered_agents,
                    "functional_agents": self.functional_agents,
                }
                self.redis_client.set(
                    PMCAEnvConfig.REDIS_AGENT_REGISTRY_KEY,
                    json.dumps(registry_to_cache),
                )
                logger.success("注册表已成功创建并存入 Redis 缓存。")
        except Exception as e:
            logger.error(f"处理智能体注册表时发生错误: {e}")
            raise

    async def _initialize_agent_memories(self):
        """
        为所有已注册的 functional agent 初始化 mem0 实例。
        这是一个轻量级操作，主要是创建本地服务对象。
        """
        logger.info("正在为所有功能性智能体初始化记忆服务...")
        for agent_name in self.functional_agents.keys():
            PMCAMem0LocalService.memory(agent_name)
        logger.success("所有功能性智能体的记忆服务均已准备就绪。")


# 创建并导出一个全局唯一的运行时实例
runtime = PMCARuntime()
