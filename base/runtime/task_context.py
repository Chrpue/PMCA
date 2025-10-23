from __future__ import annotations
from typing import TYPE_CHECKING, Optional

from autogen_core import SingleThreadedAgentRuntime

if TYPE_CHECKING:
    from core.assistant.factory import PMCAAssistantFactory
    from base.runtime.system_workbench import PMCATaskWorkbench
    from base.configs import PMCAEnvConfig
    from core.client import LLMFactory


class PMCATaskContext:
    """
    纯粹的数据容器，用于封装单个任务所需的所有上下文和资源。
    """

    _runtime_started: bool = False

    def __init__(
        self,
        task_id: str,
        task_mission: str,
        task_runtime: SingleThreadedAgentRuntime,
        task_env: "PMCAEnvConfig",
        task_workbench: "PMCATaskWorkbench",
        llm_factory: "LLMFactory",
    ):
        self.task_id = task_id
        self.task_mission = task_mission
        self.task_runtime = task_runtime
        self.task_env = task_env
        self.task_workbench = task_workbench
        self.llm_factory = llm_factory
        self.assistant_factory: Optional["PMCAAssistantFactory"] = None

    async def start_runtime(self) -> None:
        """幂等启动 SingleThreadedAgentRuntime。"""
        if not self._runtime_started:
            self.task_runtime.start()
            self._runtime_started = True

    async def stop_runtime(self) -> None:
        """幂等关闭，等待队列清空后停机。"""
        if self._runtime_started:
            await self.task_runtime.stop_when_idle()
            self._runtime_started = False

    async def ensure_runtime_started(self) -> None:
        """需要时再懒启动（对上层最友好）。"""
        if not self._runtime_started:
            self.task_runtime.start()
            self._runtime_started = True

    async def __aenter__(self) -> "PMCATaskContext":
        await self.ensure_runtime_started()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> Optional[bool]:
        await self.stop_runtime()
        return None
