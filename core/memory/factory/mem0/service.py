# 文件路径: core/memory/factory/mem0/service.py
# 这是基于您的优秀代码整合的最终版本

import copy
import re
import threading
from typing import Any, Dict, List, Optional

from loguru import logger

# 确保这些导入路径与您项目结构一致
try:
    from autogen_ext.memory.mem0 import Mem0Memory
    from base.configs import PMCAMem0LocalConfig
    from autogen_core.memory import MemoryContent, MemoryMimeType
except ImportError as e:
    raise ImportError(
        f"依赖导入失败: {e}。请确保 'autogen-ext[mem0-local]' 已安装。"
    ) from e


class PMCAMem0LocalService:
    """
    一个稳健的、为每个智能体提供独立 Mem0 实例的工厂服务。
    - 解决了 mem0 库内部的 collection_name 污染 bug。
    - 使用双重检查锁确保了线程安全。
    - 提供了清晰的配置构建和实例创建流程。
    """

    _base_config: Dict[str, Any] = PMCAMem0LocalConfig

    _instances: Dict[str, Mem0Memory] = {}
    _lock: threading.Lock = threading.Lock()

    USE_COLLECTION_AS_USER_ID: bool = True

    @staticmethod
    def _agent_to_collection(agent_name: str) -> str:
        """将智能体名称规范化为安全的数据库集合名称。"""
        return re.sub(
            r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", "_", agent_name
        ).lower()

    @classmethod
    def _build_config_for_agent(cls, agent_name: str) -> Dict[str, Any]:
        """
        基于基础模板，为指定的智能体创建一份“独立且干净”的配置。
        此方法在实例创建前就强制修正 collection_name，以规避底层库的 bug。
        """
        cfg = copy.deepcopy(cls._base_config)
        collection = cls._agent_to_collection(agent_name)

        vs_config = cfg.setdefault("vector_store", {}).setdefault("config", {})
        vs_config["collection_name"] = collection

        return cfg

    @classmethod
    def _make_instance(cls, agent_name: str) -> Mem0Memory:
        """
        真正地创建一个新的 Mem0Memory 实例（仅在缓存缺失时被调用）。
        """
        cfg = cls._build_config_for_agent(agent_name)
        collection = cfg["vector_store"]["config"]["collection_name"]

        user_id = collection if cls.USE_COLLECTION_AS_USER_ID else agent_name

        logger.info(
            f"创建新的 mem0 实例: agent='{agent_name}', user_id='{user_id}', collection='{collection}'"
        )
        return Mem0Memory(user_id=user_id, is_cloud=False, config=cfg)

    @classmethod
    def memory(cls, agent_name: str) -> Mem0Memory:
        """
        获取（如果不存在则创建）指定智能体的 Mem0Memory 单例。
        """
        if agent_name in cls._instances:
            return cls._instances[agent_name]

        with cls._lock:
            if agent_name not in cls._instances:
                cls._instances[agent_name] = cls._make_instance(agent_name)
            return cls._instances[agent_name]

    @classmethod
    async def add_memory(
        cls, agent_name: str, content: str, metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        mem = cls.memory(agent_name)
        mem_content = MemoryContent(
            content=content,
            mime_type="text/plain",
            metadata=metadata or {},
        )
        await mem.add(mem_content)

    @classmethod
    async def retrieve_memory(
        cls, agent_name: str, query: str, top_k: int = 5, **kwargs
    ) -> List[Any]:
        mem = cls.memory(agent_name)
        result = await mem.query(query, limit=top_k, **kwargs)
        return result.results

    @classmethod
    async def clear_memory(cls, agent_name: str) -> None:
        mem = cls.memory(agent_name)
        await mem.clear()

    @classmethod
    async def shutdown(cls):
        instance_count = len(cls._instances)
        if instance_count > 0:
            logger.info(f"正在关闭 {instance_count} 个 mem0 实例...")
            cls._instances.clear()
            logger.success("所有 mem0 实例已关闭，缓存已清空。")
