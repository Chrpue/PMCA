import json
import requests
from loguru import logger
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
from pydantic import BaseModel

from base.knowledge.decision import PMCAAgentsDecisionCriticKnowledge


class PMCAAgentsDecisionCriticLRMemory(Memory):
    async def clear(self) -> None:
        pass

    async def close(self) -> None:
        pass

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
        retrieve = PMCAAgentsDecisionCriticKnowledge.query(query_str)

        return MemoryQueryResult(
            results=[
                MemoryContent(
                    content=retrieve,
                    mime_type=MemoryMimeType.TEXT,
                )
            ]
        )

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
            memory_context = "\n根据我的回忆:\n" + "\n".join(memory_strings)

            # Add to context
            await model_context.add_message(SystemMessage(content=memory_context))
        return UpdateContextResult(memories=query_results)
