# service.py

import asyncio
import copy
import re
import threading
from typing import Any, Dict, Optional

from autogen_ext.memory.mem0 import Mem0Memory
from autogen_core.memory import MemoryContent
from loguru import logger

# 导入你的 mem0 配置文件
# 请确保这个路径是正确的，或者将配置直接写在这里
from base.configs import 


class PMCAMem0LocalService:
    """
    一个线程安全的单例服务，用于管理多个智能体的 Mem0 记忆实例。
    每个智能体都拥有自己独立的、基于 Qdrant collection 的记忆空间。
    """

    _instances: Dict[str, Mem0Memory] = {}
    _lock = threading.Lock()
    _is_shut_down = False

    @staticmethod
    def _agent_name_to_collection(agent_name: str) -> str:
        """
        将驼峰式命名 (CamelCase) 的智能体名称转换为蛇形命名 (snake_case)。
        例如: 'PMCATriage' -> 'pmca_triage'
        """
        if not agent_name.startswith("PMCA"):
            logger.warning(
                f"Agent name '{agent_name}' does not start with 'PMCA'. Using it as is."
            )

        # 将 'PMCA' 前缀替换为 'pmca_'
        s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", agent_name)
        return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()

    @classmethod
    def _create_instance(cls, agent_name: str) -> Mem0Memory:
        """
        为指定的智能体创建一个新的 Mem0Memory 实例。
        """
        logger.debug(f"Creating new memory instance for agent: '{agent_name}'")

        # 1. 深拷贝基础配置，防止修改影响其他实例
        config = copy.deepcopy(.PMCAMem0LocalConfig)

        # 2. 验证并设置 Qdrant provider
        vector_store_config = config.get("vector_store", {})
        if vector_store_config.get("provider") != "qdrant":
            raise ValueError(
                "Configuration error: mem0 vector_store provider must be 'qdrant'."
            )

        # 3. 为智能体生成并注入专属的 collection_name
        collection_name = cls._agent_name_to_collection(agent_name)
        vector_store_config.setdefault("config", {})["collection_name"] = (
            collection_name
        )

        logger.info(
            f"Agent '{agent_name}' is mapped to Qdrant collection '{collection_name}'"
        )

        # 4. 使用配置创建 Mem0Memory 实例
        # user_id 在 Mem0 本地版中通常用于标识用户，我们用它来关联 agent，使其更直观
        return Mem0Memory(user_id=agent_name, is_cloud=False, config=config)

    @classmethod
    def get_memory(cls, agent_name: str) -> Mem0Memory:
        """
        获取指定智能体的记忆实例。如果实例不存在，则创建并缓存它。
        这是一个线程安全的方法。
        """
        if cls._is_shut_down:
            raise RuntimeError(
                "Memory service has been shut down. Cannot get new memory instances."
            )

        # 首先在无锁的情况下进行快速检查
        if agent_name in cls._instances:
            return cls._instances[agent_name]

        # 如果实例不存在，则加锁进行创建
        with cls._lock:
            # 再次检查，防止在等待锁的过程中其他线程已经创建了实例
            if agent_name not in cls._instances:
                cls._instances[agent_name] = cls._create_instance(agent_name)
            return cls._instances[agent_name]

    @classmethod
    async def add_memory(
        cls, agent_name: str, content: str, metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        向指定智能体的记忆中添加一条新内容。
        """
        if cls._is_shut_down:
            raise RuntimeError(
                "Memory service has been shut down. Cannot add new memory."
            )

        logger.debug(f"Adding memory for agent '{agent_name}'...")

        # 1. 获取该智能体的记忆实例
        memory_instance = cls.get_memory(agent_name)

        # 2. 构造记忆内容
        memory_content = MemoryContent(
            content=content, mime_type="text/plain", metadata=metadata or {}
        )

        # 3. 调用实例的 add 方法
        await memory_instance.add(memory_content)
        logger.success(f"Successfully submitted memory for agent '{agent_name}'.")

    @classmethod
    def shutdown(cls):
        """
        关闭记忆服务，清理所有缓存的实例。
        注意：这是一个同步方法，它会清除引用，允许垃圾回收器工作。
        """
        with cls._lock:
            if not cls._is_shut_down:
                logger.info(
                    f"Shutting down PMCAMemoryService, clearing {len(cls._instances)} cached instances."
                )
                cls._instances.clear()
                cls._is_shut_down = True
                logger.success("PMCAMemoryService has been shut down.")

