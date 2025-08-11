import json
from typing import Optional, List, Any

from autogen_core import CancellationToken
from autogen_core.memory import (
    MemoryQueryResult,
    UpdateContextResult,
    Memory,
    MemoryContent,
    MemoryMimeType,
)
from autogen_core.models import SystemMessage
from autogen_core.tools import Workbench, ToolResult


class PMCAAgentsGraphMemory(Memory):
    async def clear(self) -> None:
        pass

    async def close(self) -> None:
        pass

    def __init__(self, workbench: Workbench):
        self.workbench = workbench

    async def add(
        self,
        content: MemoryContent,
        cancellation_token: CancellationToken | None = None,
    ):
        pass

    async def query(
        self,
        query_str: str,
        cancellation_token: CancellationToken | None = None,
        **kwargs: Any,
    ) -> MemoryQueryResult:
        resp = await self.workbench.call_tool(
            name="search_memories",
            arguments={"keyword": query_str},
        )
        #  解包 ToolResult
        if isinstance(resp, ToolResult):
            text_results = resp.result
        else:
            text_results = resp
        contents: List[MemoryContent] = []
        for item in text_results[1:]:
            raw = item.content
            contents.append(
                MemoryContent(
                    content=raw,
                    mime_type=MemoryMimeType.TEXT,
                )
            )
        return MemoryQueryResult(results=contents)

    async def update_context(self, model_context):
        messages = await model_context.get_messages()

        if not messages:
            return UpdateContextResult(memories=MemoryQueryResult(results=[]))
        last_message = messages[-1]
        query_results = await self.query(last_message.content)  # type: ignore
        if query_results.results:
            memory_strings = [
                f"{i}. {str(memory.content)}"
                for i, memory in enumerate(query_results.results, 1)
            ]
            memory_context = "\n检索到记忆信息:\n" + "\n".join(memory_strings)

            # Add to context
            await model_context.add_message(SystemMessage(content=memory_context))
        return UpdateContextResult(memories=query_results)
