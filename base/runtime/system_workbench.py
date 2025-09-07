import os
import uuid
import shutil
import tempfile
from pathlib import Path
from typing import Dict, Any, List

from loguru import logger

from autogen_core.tools import StaticWorkbench, BaseTool
from autogen_ext.code_executors.docker import DockerCommandLineCodeExecutor

from base.configs import PMCAEnvConfig


class PMCATaskWorkbench(StaticWorkbench):
    """
    一个为单次任务提供隔离环境的、继承自 StaticWorkbench 的综合性工作台。

    它具备双重职责：
    1.  作为标准的 AutoGen Workbench，管理一套提供给智能体的、与任务隔离的工具集
        （如代码执行器、文件系统工具）。
    2.  作为一个任务级的上下文状态管理器，提供 get_item 和 set_item 方法，
        供我们的程序逻辑（如 GraphFlow）直接调用，以控制流程。
    """

    def __init__(self, task_id: str, work_dir: str):
        self.task_id = task_id
        self.work_dir = Path(work_dir)

        # 1. 初始化用于程序流程控制的键值存储
        self._kv_storage: Dict[str, Any] = {}
        logger.info(f"任务 [{self.task_id}] 的工作台已创建，工作目录: {self.work_dir}")

        # 2. 组装所有需要提供给智能体的工具
        tools = self._create_tool_set()

        # 3. 调用父类的构造函数，将工具集注册到 Workbench 中
        super().__init__(tools=tools)

    # --- 为程序逻辑提供的状态管理方法 ---
    def set_item(self, key: str, value: Any):
        """(供程序调用) 在工作台的键值存储中设置一项。"""
        logger.debug(f"任务 [{self.task_id}] 上下文设置: {key} = {value}")
        self._kv_storage[key] = value

    def get_item(self, key: str) -> Any:
        """(供程序调用) 从工作台的键值存储中获取一项。"""
        value = self._kv_storage.get(key)
        logger.debug(f"任务 [{self.task_id}] 上下文获取: {key} -> {value}")
        return value

    def _create_tool_set(self) -> List[BaseTool]:
        """(内部方法) 创建并配置所有与此任务隔离的工具。"""
        tool_list: List[BaseTool] = []

        # 工具一：隔离的代码执行器
        logger.info(f"任务 [{self.task_id}] 正在创建专属代码执行器工具...")
        task_specific_volumes = {
            str(self.work_dir): {"bind": "/workspace", "mode": "rw"}
        }
        merged_volumes = {**PMCAEnvConfig.DOCKER_EXTRA_VOLUMES, **task_specific_volumes}
        # code_executor = DockerCommandLineCodeExecutor(
        #     image=PMCAEnvConfig.DOCKER_IMAGE,
        #     container_name=f"{PMCAEnvConfig.DOCKER_CONTAINER_NAME}-{self.task_id}",
        #     timeout=PMCAEnvConfig.DOCKER_TIMEOUT,
        #     work_dir="/workspace",
        #     extra_volumes=merged_volumes,
        #     auto_remove=True,
        # )
        # tool_list.append(code_executor)

        # 工具二：文件系统及其他 MCP 工具
        # 注意：这里我们直接使用 AgentFactory 中的逻辑来获取 McpWorkbench 实例
        # 这要求 AgentFactory 能够被访问。我们将在 manager 中处理这个问题。

        # 暂时留空，我们将在下一步重构 AgentFactory 时填充这里

        logger.success(f"为任务 [{self.task_id}] 创建了 {len(tool_list)} 个核心工具。")
        return tool_list

    def cleanup(self):
        """清理此工作台创建的所有资源。"""
        logger.info(f"正在清理任务 [{self.task_id}] 的工作台资源...")
        try:
            # 停止代码执行器（如果正在运行）
            # 注意：autogen 0.7.4 的 DockerCodeExecutor 没有显式的 stop 方法，
            # auto_remove=True 会在完成时自动清理容器。
            shutil.rmtree(self.work_dir)
            logger.success(
                f"任务 [{self.task_id}] 的工作目录 {self.work_dir} 已被删除。"
            )
        except OSError as e:
            logger.error(f"清理工作目录 {self.work_dir} 失败: {e}")


class PMCATaskWorkbenchManager:
    """负责创建和管理 PMCATaskWorkbench 实例的单例管理器。"""

    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(PMCATaskWorkbenchManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._base_dir: str = tempfile.gettempdir()
        logger.info(f"任务工作台管理器已初始化，基础目录: {self._base_dir}")
        self._initialized = True

    def create_workbench(self) -> PMCATaskWorkbench:
        """为新任务创建一个全新的、隔离的 PMCATaskWorkbench 实例。"""
        task_id = str(uuid.uuid4())[:8]
        work_dir = os.path.join(self._base_dir, "pmca_tasks", task_id)
        os.makedirs(work_dir, exist_ok=True)
        return PMCATaskWorkbench(task_id=task_id, work_dir=work_dir)

