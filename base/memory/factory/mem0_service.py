from loguru import logger
from typing import List, Dict, Any

try:
    from autogen_ext.memory.mem0 import Mem0Memory
    from base.memory.configs import PMCAMem0LocalConfig
except ImportError as e:
    raise ImportError(
        f"依赖导入失败: {e}。请确保 'autogen-ext[mem0-local]' 已安装，并且 PMCAMem0LocalConfig 路径正确。"
    )


class PMCAMem0LocalService:
    """
    该类遵循单一职责原则:
    1.  持有一个标准的本地 mem0 服务配置。
    2.  根据请求，为任意指定的智能体名称创建一个专属的、隔离的 Mem0Memory 实例。

    该类是无状态的，不维护任何智能体注册表，将智能体的生命周期管理完全解耦给 AgentFactory。
    """

    _mem0_config: Dict[str, Any] = PMCAMem0LocalConfig

    @classmethod
    def memory(cls, agent_name: str) -> Mem0Memory:
        """
        为一个智能体创建专属的 Mem0 记忆组件。

        这是一个类方法，因为该服务是无状态的，无需实例化。

        Args:
            agent_name (str): 智能体的唯一名称，将用作 mem0 的 user_id。

        Returns:
            List[Mem0Memory]: 包含单个配置好的 Mem0Memory 实例的列表，
                              可直接用于 autogen.AssistantAgent 的 `memory` 参数。
        """
        logger.info(f"为智能体 '{agent_name}' 创建专属的 Mem0 记忆实例...")

        # 使用 **cls._mem0_config 解包字典，将配置传递给 Mem0Memory
        instance = Mem0Memory(
            user_id=agent_name,
            is_cloud=False,
            config={**cls._mem0_config},
        )

        # autogen 的 memory 参数期望一个列表
        return instance
