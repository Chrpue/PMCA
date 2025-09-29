from __future__ import annotations
from typing import Dict, List, Protocol, Optional
import threading
from autogen_core.tools import FunctionTool


class PMCAToolProvider(Protocol):
    def for_assistant(self, agent_name: str) -> List[FunctionTool]: ...


class _SingletonMeta(type):
    """线程安全的单例元类：第一次实例化时加锁，确保只构造一次。"""

    _instance: Optional["PMCAToolRegistry"] = None
    _lock = threading.Lock()

    def __call__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__call__(*args, **kwargs)
        return cls._instance


class PMCAToolRegistry(metaclass=_SingletonMeta):
    """注册中心：按智能体名维护 Provider 列表；并发安全。"""

    def __init__(self) -> None:
        self._assistant_providers: Dict[str, List[PMCAToolProvider]] = {}
        self._default_providers: List[PMCAToolProvider] = []
        self._rwlock = threading.RLock()

    def register_for_default(self, provider: PMCAToolProvider) -> None:
        with self._rwlock:
            self._default_providers.append(provider)

    def register_for_assistant(
        self, assistant_name: str, provider: PMCAToolProvider
    ) -> None:
        with self._rwlock:
            self._assistant_providers.setdefault(assistant_name, []).append(provider)

    def providers(self, assistant_name: str) -> List[PMCAToolProvider]:
        """
        获取智能体的工具箱
        """
        with self._rwlock:
            specific = list(self._assistant_providers.get(assistant_name, []))
            default = list(self._default_providers)
        return [*specific, *default]

    def clear_all(self) -> None:
        """
        清空智能体与工具注册的关系
        """
        with self._rwlock:
            self._assistant_providers.clear()
            self._default_providers.clear()
