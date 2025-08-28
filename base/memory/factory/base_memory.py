from typing import Any, List, Optional
from autogen_core.memory import Memory
from autogen_core import CancellationToken
from autogen_core.memory import (
    MemoryQueryResult,
    UpdateContextResult,
    MemoryContent,
    MemoryMimeType,
)

from autogen_core.models import SystemMessage
from loguru import logger
from .memory_manager import PMCAMirixMemoryManager


class PMCAMirixMemory(Memory):
    """
    一个自定义的AutoGen Memory类，用于将每个智能体的记忆连接到外部的Mirix服务。
    该类严格遵循用户提供的 PMCAAgentsDecisionLRMemory 示例模式。
    """

    def __init__(self, agent_name: str, memory_manager: PMCAMirixMemoryManager):
        """
        初始化一个与特定智能体绑定的Mirix记忆实例。
        """
        super().__init__()
        self.agent_name = agent_name
        self.memory_manager = memory_manager

        # 在创建时，确保该智能体已在Mirix中注册
        self.memory_manager.register_agent_memory(self.agent_name)
        logger.success(
            f"为智能体 '{self.agent_name}' 成功创建并初始化 PMCAMirixMemory。"
        )

    async def add(
        self,
        content: MemoryContent,
        cancellation_token: CancellationToken | None = None,
    ):
        """
        当对话历史更新时，此方法被调用以“记忆”新信息。
        我们将在这里把对话内容发送给Mirix进行存储。
        """
        if content.mime_type == MemoryMimeType.TEXT and isinstance(
            content.content, str
        ):
            # 为了避免将自身的记忆上下文存入，我们只存储非系统消息
            # 这里的逻辑可以根据需要进一步细化
            if content.role != "system":  # type: ignore
                self.memory_manager.remember(
                    self.agent_name,
                    f"对话历史记录: {content.role} 说 '{content.content}'",  # type: ignore
                )
        return

    async def query(
        self,
        query_str: str,
        cancellation_token: CancellationToken | None = None,
        **kwargs: Any,
    ) -> MemoryQueryResult:
        """
        根据查询字符串从Mirix检索信息。
        """
        retrieved_memory = self.memory_manager.recall(self.agent_name, query_str)

        if retrieved_memory:
            return MemoryQueryResult(
                results=[
                    MemoryContent(
                        content=retrieved_memory,
                        mime_type=MemoryMimeType.TEXT,
                    )
                ]
            )
        return MemoryQueryResult(results=[])

    async def update_context(self, model_context: Any) -> UpdateContextResult:
        """
        在LLM调用之前更新上下文。这是实现“回忆”的关键。
        """
        messages = await model_context.get_messages()
        if not messages:
            return UpdateContextResult(memories=MemoryQueryResult(results=[]))

        last_message = messages[-1]
        if not isinstance(last_message.content, str):
            return UpdateContextResult(memories=MemoryQueryResult(results=[]))

        query_results = await self.query(last_message.content)

        if query_results.results:
            memory_strings = [
                f"{i}. {str(memory.content)}"
                for i, memory in enumerate(query_results.results, 1)
            ]
            memory_context = (
                "\n--- 根据我的长期记忆 ---\n" + "\n".join(memory_strings) + "\n---"
            )

            await model_context.add_message(SystemMessage(content=memory_context))
            logger.info(f"为 '{self.agent_name}' 成功注入Mirix记忆上下文。")

        return UpdateContextResult(memories=query_results)

    async def clear(self) -> None:
        pass

    async def close(self) -> None:
        pass
