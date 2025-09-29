from __future__ import annotations
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from core.assistant.factory import PMCAAssistantFactory
    from base.runtime.system_workbench import PMCATaskWorkbench
    from base.configs import PMCAEnvConfig
    from core.client import LLMFactory


class PMCATaskContext:
    """
    一个纯粹的数据容器，用于封装单个任务所需的所有上下文和资源。
    """

    def __init__(
        self,
        task_id: str,
        task_mission: str,
        task_env: "PMCAEnvConfig",
        task_workbench: "PMCATaskWorkbench",
        llm_factory: "LLMFactory",
    ):
        self.task_id = task_id
        self.task_mission = task_mission
        self.task_env = task_env
        self.task_workbench = task_workbench
        self.llm_factory = llm_factory
        self.assistant_factory: Optional["PMCAAssistantFactory"] = None
