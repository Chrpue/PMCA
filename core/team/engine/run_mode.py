import asyncio
from functools import wraps
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional, Tuple, Union

from autogen_agentchat.messages import BaseAgentEvent, BaseChatMessage
from autogen_agentchat.base import TaskResult
from loguru import logger


def dispatch_run_mode(fn):
    """
    一个简化的装饰器，不再需要参数。
    它负责根据 'mode' 关键字参数来处理被装饰函数返回的异步生成器(stream)。
    """

    @wraps(fn)
    async def _wrapper(self, *args, **kwargs):
        mode = kwargs.pop("mode", "service")
        background = kwargs.pop("background", False)
        custom_callable: Optional[Callable] = kwargs.pop("custom_callable", None)

        stream: AsyncGenerator[
            Union[BaseAgentEvent, BaseChatMessage, TaskResult], None
        ] = await fn(self, *args, **kwargs)

        if mode == "console":
            from autogen_agentchat.ui import Console

            if background:
                return asyncio.create_task(Console(stream))
            return await Console(stream)  # -> TaskResult

        # --- service 模式：自定义一轮一轮捕获 ---
        rounds: List[List[Union[BaseAgentEvent, BaseChatMessage]]] = []
        buf: List[Union[BaseAgentEvent, BaseChatMessage]] = []
        last_speaker = None
        round_index = 0
        final_result: Optional[TaskResult] = None

        async for item in stream:
            if isinstance(item, TaskResult):
                if buf:
                    rounds.append(buf)
                    if custom_callable:
                        custom_callable(round_index, buf)
                final_result = item
                break

            if item.__class__.__name__ == "ModelClientStreamingChunkEvent":
                continue

            current_speaker = getattr(item, "source", None)
            if (
                last_speaker is not None
                and current_speaker
                and current_speaker != last_speaker
            ):
                rounds.append(buf)
                if custom_callable:
                    custom_callable(round_index, buf)
                round_index += 1
                buf = []

            buf.append(item)
            last_speaker = current_speaker or last_speaker

        if final_result is None:
            if buf:  # 处理流结束但没有TaskResult的边界情况
                rounds.append(buf)
                if custom_callable:
                    custom_callable(round_index, buf)
            raise RuntimeError("Stream ended without a TaskResult.")

        return {"rounds": rounds, "result": final_result}

    return _wrapper
