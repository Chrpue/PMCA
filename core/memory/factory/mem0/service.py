# 文件路径: core/memory/factory/mem0/service.py
# 最终决定版

import copy
import re
import threading
from loguru import logger
from typing import Any, Dict, List, Optional
from tenacity import (
    retry,
    wait_exponential,
    stop_after_attempt,
    retry_if_exception_type,
)
from sqlalchemy.exc import OperationalError, InterfaceError


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
        """
        cfg = copy.deepcopy(cls._base_config)
        collection = cls._agent_to_collection(agent_name)
        vs_config = cfg.setdefault("vector_store", {}).setdefault("config", {})
        vs_config["collection_name"] = collection
        return cfg

    @classmethod
    def _make_instance(cls, agent_name: str) -> Mem0Memory:
        """
        创建一个新的 Mem0Memory 实例，并包含构造后的强制修正逻辑。
        """
        cfg = cls._build_config_for_agent(agent_name)
        intended_collection = cfg["vector_store"]["config"]["collection_name"]
        user_id = intended_collection if cls.USE_COLLECTION_AS_USER_ID else agent_name

        logger.debug(
            f"正在创建 mem0 实例: agent='{agent_name}', 期望的 collection='{intended_collection}'"
        )

        instance = Mem0Memory(user_id=user_id, is_cloud=False, config=cfg)

        try:
            client = getattr(instance, "_client", None)
            if client:
                top_level_config = getattr(client, "config", None)
                if top_level_config and hasattr(top_level_config, "vector_store"):
                    vector_store_config_obj = getattr(
                        top_level_config.vector_store, "config", None
                    )
                    if vector_store_config_obj:
                        actual_collection = getattr(
                            vector_store_config_obj, "collection_name", None
                        )
                        if actual_collection != intended_collection:
                            logger.warning(
                                f"检测到 mem0 库配置污染: collection_name 被设置为 '{actual_collection}'。"
                                f"正在为 agent '{agent_name}' 强制修正回 '{intended_collection}'..."
                            )
                            setattr(
                                vector_store_config_obj,
                                "collection_name",
                                intended_collection,
                            )
                            logger.success(
                                f"修正成功: agent '{agent_name}' 的 collection_name 已被设置为 '{intended_collection}'。"
                            )
        except Exception as e:
            logger.error(f"尝试修正 collection_name 时发生意外错误: {e}")

        return instance

    @classmethod
    def memory(cls, agent_name: str) -> Mem0Memory:
        """
        获取（如果不存在则创建）指定智能体的 Mem0Memory 缓存单例。
        注意：此方法主要用于非写入操作，如查询。
        """
        if agent_name in cls._instances:
            return cls._instances[agent_name]
        with cls._lock:
            if agent_name not in cls._instances:
                cls._instances[agent_name] = cls._make_instance(agent_name)
            return cls._instances[agent_name]

    # [最终核心修复]：让 add_memory 方法总是创建一个全新的实例来写入，保证连接新鲜
    @classmethod
    @retry(
        reraise=True,
        wait=wait_exponential(multiplier=0.5, min=0.5, max=8),
        stop=stop_after_attempt(5),
        retry=retry_if_exception_type((OperationalError, InterfaceError)),
    )
    async def add_memory(
        cls, agent_name: str, content: str, metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        通过创建一个临时的、全新的 mem0 实例来安全地添加记忆。
        这可以确保我们使用的是一个新鲜的数据库连接，避免因连接池中连接失效而导致的静默失败。
        """
        logger.info(f"[mem0] 新实例写入（带重试） agent={agent_name}")
        temp_instance = cls._make_instance(agent_name)
        mem_content = MemoryContent(
            content=content, mime_type="text/plain", metadata=metadata or {}
        )
        await temp_instance.add(mem_content)

    @classmethod
    async def shutdown(cls):
        instance_count = len(cls._instances)
        if instance_count > 0:
            logger.info(f"正在关闭 {instance_count} 个缓存的 mem0 实例...")
            cls._instances.clear()
            logger.success("所有缓存的 mem0 实例已关闭。")
