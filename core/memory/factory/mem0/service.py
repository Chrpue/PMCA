import copy
import re
import threading
from typing import Dict

from loguru import logger
from autogen_ext.memory.mem0 import Mem0Memory
from base.configs import mem0config


class PMCAMem0LocalService:
    """
    线程安全的 Mem0Memory 工厂/缓存：
    - 单例：同一个 assistant_name 只创建一个 Mem0Memory
    - 线程安全：双重检查 + 进程内锁
    """

    _instances: Dict[str, Mem0Memory] = {}
    _lock = threading.Lock()

    @staticmethod
    def _assistant_name_to_unified_id(assistant_name: str) -> str:
        """
        将驼峰式名转 snake_case，作为统一的 user_id（与 collection_name 解耦）
        """
        s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", assistant_name)
        return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()

    @classmethod
    def instance(cls, assistant_name: str) -> Mem0Memory:
        """
        创建新的 Mem0Memory 实例。
        """
        try:
            unified_id = cls._assistant_name_to_unified_id(assistant_name)
            cfg = copy.deepcopy(mem0config.PMCAMem0LocalConfig)  # 仅防御性拷贝

            try:
                cfg.setdefault("vector_store", {}).setdefault("config", {}).update(
                    collection_name=unified_id
                )
            except Exception as e:
                logger.error(f"[Mem0] set collection_name failed: {e}")
                raise

            memory = Mem0Memory(
                user_id=unified_id,
                is_cloud=False,
                config=cfg,
            )
            return memory
        except Exception as e:
            logger.error(f"[Mem0] create instance failed for '{assistant_name}': {e}")
            raise

    @classmethod
    def memory(cls, assistant_name: str) -> Mem0Memory:
        """
        获取或构建指定智能体的单例记忆实例（线程安全）
        """
        inst = cls._instances.get(assistant_name)
        if inst is not None:
            return inst

        with cls._lock:
            inst = cls._instances.get(assistant_name)
            if inst is None:
                inst = cls.instance(assistant_name)
                cls._instances[assistant_name] = inst
            return inst

