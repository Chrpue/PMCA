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


class LightRAGConfig(BaseModel):
    endpoint: str = "http://localhost:13004/query"
    headers: dict = {"Content-Type": "application/json"}
    payload: dict = {
        "query": "",
        "mode": "naive",  # 换成 hybrid，优先尝试图 + 向量综合
        "top_k": 3,  # 提高召回条数
        "only_need_context": False,
        "only_need_prompt": False,
        "response_type": "string",
        "stream": False,
        "user_prompt": """你是一个负责掌管记忆的专家，你的任务是根据用户的查询内容，提供最相关的记忆上下文，但是不要做出任何决断，仅仅提供记忆.""",
    }


class PMCAAgentsDecisionGraphMemory(Memory):
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
        config = LightRAGConfig()
        config.payload["query"] = query_str

        resp = await self.workbench.call_tool(
            name="query_document",
            arguments=config.payload,
        )

        logger.info(resp)

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
            memory_context = "\n根据我的回忆:\n" + "\n".join(memory_strings)

            # Add to context
            await model_context.add_message(SystemMessage(content=memory_context))
        return UpdateContextResult(memories=query_results)
