# core/memory/factory/mem0/service.py

import copy
import re
import threading
from typing import Any, Dict, List, Optional

from loguru import logger

# 确认这些是项目中的正确导入路径
from autogen_ext.memory.mem0 import Mem0Memory
from autogen_core.memory import MemoryContent, MemoryMimeType, MemoryQueryResult

# 导入你的 mem0 配置文件
from base.configs import mem0config


class PMCAMem0LocalService:
    """
    一个线程安全的服务，用于管理和访问多个智能体 (Assistant) 的 Mem0 记忆实例。
    (最终定稿版)
    """

    _instances: Dict[str, Mem0Memory] = {}
    _lock = threading.Lock()

    @staticmethod
    def _assistant_name_to_unified_id(assistant_name: str) -> str:
        """
        将驼峰式命名的智能体 (Assistant) 名称转换为统一的蛇形命名 (snake_case) ID。
        """
        s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", assistant_name)
        return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()

    @classmethod
    def instance(cls, assistant_name: str) -> Mem0Memory:
        """
        为指定的智能体创建一个新的、配置隔离的 Mem0Memory 实例。
        """
        try:
            config = copy.deepcopy(mem0config.PMCAMem0LocalConfig)
            vector_store_config = config.get("vector_store", {})

            if vector_store_config.get("provider") != "qdrant":
                raise ValueError(
                    "Configuration error: mem0 vector_store provider must be 'qdrant'."
                )

            # 统一生成蛇形ID
            unified_id = cls._assistant_name_to_unified_id(assistant_name)

            # 将统一ID同时用于 collection_name 和 user_id
            vector_store_config.setdefault("config", {})["collection_name"] = unified_id

            return Mem0Memory(user_id=unified_id, is_cloud=False, config=config)

        except Exception as e:
            logger.error(
                f"Failed to create memory instance for assistant '{assistant_name}': {e}"
            )
            raise

    @classmethod
    def memory(cls, assistant_name: str) -> Mem0Memory:
        """
        获取指定智能体的记忆实例 (线程安全)。
        """
        if assistant_name in cls._instances:
            return cls._instances[assistant_name]

        with cls._lock:
            if assistant_name not in cls._instances:
                cls._instances[assistant_name] = cls.instance(assistant_name)
            return cls._instances[assistant_name]
