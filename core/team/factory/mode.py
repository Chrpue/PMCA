from __future__ import annotations

from typing import AsyncGenerator, Union
from autogen_agentchat.base import TaskResult
from autogen_agentchat.messages import BaseAgentEvent, BaseChatMessage
from autogen_agentchat.ui import Console


async def consume_console(
    stream: AsyncGenerator[Union[BaseAgentEvent, BaseChatMessage, TaskResult], None],
) -> TaskResult:
    """
    用 AutoGen 自带 Console 实时打印并消费这条流，返回最终 TaskResult。
    Console 是官方推荐的流消费者。
    """
    return await Console(stream)


async def consume_service(
    stream: AsyncGenerator[Union[BaseAgentEvent, BaseChatMessage, TaskResult], None],
) -> TaskResult:
    """
    面向前端/服务化：逐条消费这条流（你可在此处转发到 WS/SSE/队列），
    并在末尾返回最终 TaskResult。
    """
    last: TaskResult | None = None
    async for item in stream:
        # TODO: 在这里把 item 逐条推给前端（WS/SSE/消息总线等）
        if isinstance(item, TaskResult):
            last = item
    if last is None:
        raise RuntimeError("Service consumer did not receive a final TaskResult.")
    return last

