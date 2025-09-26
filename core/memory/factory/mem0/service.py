import copy
import re
import threading
from typing import Any, Dict, List, Optional

from loguru import logger

# 确认这些是项目中的正确导入路径
from autogen_ext.memory.mem0 import Mem0Memory
from autogen_core.memory import MemoryContent, MemoryQueryResult

# 导入你的 mem0 配置文件
from base.configs import mem0config


class PMCAMem0LocalService:
    """
    一个线程安全的服务，用于管理和访问多个智能体 (Assistant) 的 Mem0 记忆实例。

    该服务基于 AutoGen 官方提供的 Mem0Memory 源码进行封装，严格使用其暴露的公共接口。
    它采用单例模式缓存每个智能体的记忆实例，并依赖底层库进行连接和生命周期管理。
    """

    _instances: Dict[str, Mem0Memory] = {}
    _lock = threading.Lock()

    @staticmethod
    def _assistant_name_to_collection(assistant_name: str) -> str:
        """
        将驼峰式命名的智能体 (Assistant) 名称转换为蛇形命名 (snake_case) 的集合名称。
        例如: 'PMCAQueryAssistant' -> 'pmca_query_assistant'
        """
        s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", assistant_name)
        return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()

    @classmethod
    def instance(cls, assistant_name: str) -> Mem0Memory:
        """
        为指定的智能体创建一个新的、配置隔离的 Mem0Memory 实例。
        此方法为内部使用，外部请调用 memory()。
        """
        try:
            config = copy.deepcopy(mem0config.PMCAMem0LocalConfig)
            vector_store_config = config.get("vector_store", {})

            if vector_store_config.get("provider") != "qdrant":
                raise ValueError(
                    "Configuration error: mem0 vector_store provider must be 'qdrant'."
                )

            collection_name = cls._assistant_name_to_collection(assistant_name)
            vector_store_config.setdefault("config", {})["collection_name"] = (
                collection_name
            )

            # 根据源码，user_id 也非常重要，它在 clear() 操作中是关键标识符。
            # 我们将 assistant_name 同时用作 user_id，确保记忆隔离。
            return Mem0Memory(user_id=assistant_name, is_cloud=False, config=config)
        except Exception as e:
            logger.error(
                f"Failed to create memory instance for assistant '{assistant_name}': {e}"
            )
            raise

    @classmethod
    def memory(cls, assistant_name: str) -> Mem0Memory:
        """
        获取指定智能体的记忆实例 (线程安全)。
        如果实例不存在，则创建并缓存。
        """
        if assistant_name in cls._instances:
            return cls._instances[assistant_name]

        with cls._lock:
            if assistant_name not in cls._instances:
                cls._instances[assistant_name] = cls.instance(assistant_name)
            return cls._instances[assistant_name]

    @classmethod
    async def add(
        cls,
        assistant_name: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        向指定智能体的记忆中添加一条新内容。
        """
        try:
            memory_instance = cls.memory(assistant_name)
            memory_content = MemoryContent(
                content=content, mime_type="text/plain", metadata=metadata or {}
            )
            await memory_instance.add(memory_content)
        except Exception as e:
            logger.error(f"Failed to add memory for assistant '{assistant_name}': {e}")

    @classmethod
    async def query(
        cls, assistant_name: str, query_text: str, limit: int = 5
    ) -> List[MemoryContent]:
        """
        在指定智能体的记忆中进行语义搜索，并返回结果列表。
        """
        try:
            memory_instance = cls.memory(assistant_name)
            # 根据源码，query 方法的 **kwargs 可以传递 limit 参数
            query_result: MemoryQueryResult = await memory_instance.query(
                query=query_text, limit=limit
            )
            return query_result.results
        except Exception as e:
            logger.error(
                f"Failed to query memory for assistant '{assistant_name}': {e}"
            )
            return []

    @classmethod
    async def clear(cls, assistant_name: str) -> None:
        """
        清空指定智能体的所有记忆。
        此操作基于 user_id，我们在创建实例时已将 assistant_name 设为 user_id。
        """
        try:
            memory_instance = cls.memory(assistant_name)
            await memory_instance.clear()
        except Exception as e:
            logger.error(
                f"Failed to clear memory for assistant '{assistant_name}': {e}"
            )

