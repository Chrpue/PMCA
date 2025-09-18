import asyncio
from functools import wraps
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional, Tuple, Union

from autogen_agentchat.messages import BaseAgentEvent, BaseChatMessage
from autogen_agentchat.base import TaskResult
from autogen_agentchat.ui import Console


def dispatch_run_mode(mode_kw: str = "mode", background_kw: str = "background"):
    def _decorator(fn):
        @wraps(fn)
        async def _wrapper(self, *args, **kwargs):
            mode = kwargs.pop(mode_kw, "service")
            background = kwargs.pop(background_kw, False)
            on_round: Optional[
                Callable[[int, List[Union[BaseAgentEvent, BaseChatMessage]]], Any]
            ] = kwargs.pop("on_round", None)

            stream: AsyncGenerator[
                Union[BaseAgentEvent, BaseChatMessage, TaskResult], None
            ] = await fn(self, *args, **kwargs)

            if mode == "console":
                # 延迟导入，避免非 console 模式的额外依赖
                from autogen_agentchat.ui import Console

                if background:
                    return asyncio.create_task(Console(stream))
                return await Console(stream)  # -> TaskResult

            # --- service 模式：自定义一轮一轮捕获 ---
            rounds: List[List[Union[BaseAgentEvent, BaseChatMessage]]] = []
            buf: List[Union[BaseAgentEvent, BaseChatMessage]] = []
            last = None
            r = 0
            final: Optional[TaskResult] = None
            async for item in stream:
                if isinstance(item, TaskResult):
                    if buf:
                        rounds.append(buf)
                        if on_round:
                            on_round(r, buf)
                    final = item
                    break
                if item.__class__.__name__ == "ModelClientStreamingChunkEvent":
                    continue
                speaker = getattr(item, "source", None)
                if last is not None and speaker and speaker != last:
                    rounds.append(buf)
                    if on_round:
                        on_round(r, buf)
                    r += 1
                    buf = []
                buf.append(item)
                last = speaker or last
            if final is None:
                if buf:
                    rounds.append(buf)
                    if on_round:
                        on_round(r, buf)
                raise RuntimeError("Stream ended without TaskResult")
            return {"rounds": rounds, "result": final}

        return _wrapper

    return _decorator
