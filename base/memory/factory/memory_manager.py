from base.memory.client import PMCAMirixClient
from typing import Dict, Optional
from loguru import logger
from utils.singleton_pattern import Singleton


class PMCAMirixMemoryManager(Singleton):
    """
    管理所有智能体与Mirix记忆服务的交互。
    这是一个单例，以确保整个应用共享同一个记忆连接和状态。
    """

    def __init__(self):
        if not hasattr(self, "initialized"):
            self.client = PMCAMirixClient()
            self.agent_to_user_id: Dict[str, str] = {}
            self.initialized = True
            logger.info("PMCAMirixMemoryManager 初始化...")
            if not self.client.check_health():
                logger.critical(
                    "无法连接到Mirix服务，请确保服务正在运行并且.env文件配置正确。"
                )
                raise ConnectionError(
                    "无法连接到Mirix服务，请确保服务正在运行并且.env文件配置正确。"
                )
            self._sync_users()

    def _sync_users(self):
        logger.info("正在从Mirix同步用户（智能体）列表...")
        mirix_users = self.client.list_users()
        for user in mirix_users:
            self.agent_to_user_id[user["name"]] = user["id"]
        logger.success(
            f"同步完成！已加载 {len(self.agent_to_user_id)} 个智能体的记忆档案。"
        )

    def register_agent_memory(self, agent_name: str):
        """为智能体注册记忆档案，如果不存在则创建。"""
        if agent_name not in self.agent_to_user_id:
            logger.info(
                f"智能体 '{agent_name}' 在Mirix中不存在，正在为其创建记忆档案..."
            )
            user = self.client.create_user(agent_name)
            if user:
                user_id = user["id"]
                self.agent_to_user_id[agent_name] = user_id
                logger.success(f"智能体 '{agent_name}' 注册成功，User ID: {user_id}")
            else:
                logger.error(f"无法为智能体 '{agent_name}' 创建Mirix user。")
                raise RuntimeError(f"无法为智能体 '{agent_name}' 创建Mirix user。")
        else:
            logger.debug(f"智能体 '{agent_name}' 的记忆档案已存在。")

    def recall(self, agent_name: str, query: str) -> Optional[str]:
        if agent_name not in self.agent_to_user_id:
            logger.warning(f"智能体 '{agent_name}' 尚未注册记忆，无法进行回忆。")
            return None

        user_id = self.agent_to_user_id[agent_name]
        logger.info(f"智能体 '{agent_name}' 正在回忆关于: '{query}'")
        response = self.client.send_message(query, user_id)

        if response and "response" in response:
            recalled_memory = response["response"]
            logger.info(f"智能体 '{agent_name}' 的回忆结果: '{recalled_memory}'")
            return recalled_memory

        logger.warning(f"智能体 '{agent_name}' 未能从记忆中找到关于 '{query}' 的内容。")
        return None

    def remember(self, agent_name: str, fact: str):
        if agent_name not in self.agent_to_user_id:
            logger.warning(f"智能体 '{agent_name}' 尚未注册记忆，无法进行记忆。")
            return

        logger.info(f"智能体 '{agent_name}' 正在记忆: '{fact}'")
        self.recall(agent_name, f"请记住以下信息: {fact}")
