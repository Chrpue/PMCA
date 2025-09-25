from __future__ import annotations
from typing import Any, Dict, List, Optional
from autogen_core.tools import FunctionTool
from autogen_core.memory import MemoryContent, MemoryMimeType
from loguru import logger

from core.memory.factory.mem0 import PMCAMem0LocalService
from core.tools.factory import PMCAToolProvider


class PMCAMem0ToolsProvider(PMCAToolProvider):
    """
    mem0 工具箱，提供针对记忆数据的基础工具方法
    """

    def for_assistant(self, assistant_name: str) -> List[FunctionTool]:
        tools: List[FunctionTool] = []

        async def mem_add(
            text: str,
            metadata: Optional[Dict[str, Any]] = None,
        ) -> Dict[str, Any]:
            """
            向该智能体的记忆库新增一条文本记忆。
            :param text: 记忆内容（纯文本）
            :param metadata: 可选键值（如 {"purpose": "triage", "biz": "PMCAOrchestrator"}）
            :return: {"ok": True}
            """
            mem = PMCAMem0LocalService.memory(assistant_name)
            content = MemoryContent(
                content=text,
                mime_type=MemoryMimeType.TEXT,
                metadata=metadata or {},
            )
            await mem.add(content)
            return {"ok": True}

        tools.append(
            FunctionTool(
                name="mem_add",
                description="为智能体添加纯文本记忆.",
                func=mem_add,
            )
        )

        async def mem_query(
            query: str,
            top_k: int = 5,
            metadata_filter: Optional[Dict[str, Any]] = None,
            **kwargs: Any,
        ) -> Dict[str, Any]:
            """
            以语义检索该智能体的记忆。
            :param query: 查询字符串
            :param top_k: 返回条数上限
            :param metadata_filter: 可选的元数据过滤（后端支持差异化）
            :param kwargs: 透传 mem0 query 的额外参数（如 rerank 等）
            :return: {"ok": True, "items": [{id?, content, score?, metadata?}, ...]}
            """
            mem = PMCAMem0LocalService.memory(assistant_name)
            res = await mem.query(
                query,
                limit=top_k,
                **({"metadata_filter": metadata_filter} if metadata_filter else {}),
                **kwargs,
            )

            items: List[Dict[str, Any]] = []
            iterable = getattr(res, "results", res or [])
            for r in iterable:
                try:
                    items.append(
                        {
                            "id": getattr(r, "id", None),
                            "content": getattr(
                                r, "content", getattr(r, "text", None) or str(r)
                            ),
                            "metadata": getattr(r, "metadata", None),
                            "score": getattr(r, "score", None),
                        }
                    )
                except Exception:
                    items.append({"content": str(r)})

            logger.debug(
                f"[mem_query] assistant={assistant_name} q={query!r} k={top_k} meta={metadata_filter}"
            )
            return {"ok": True, "items": items}

        tools.append(
            FunctionTool(
                name="mem_query",
                description="检索智能体的记忆.",
                func=mem_query,
            )
        )

        async def mem_clear() -> Dict[str, Any]:
            """
            清空该智能体的记忆。
            :return: {"ok": True}
            """
            mem = PMCAMem0LocalService.memory(assistant_name)
            await mem.clear()
            return {"ok": True}

        tools.append(
            FunctionTool(
                name="mem_clear",
                description="清空智能体的所有记忆.",
                func=mem_clear,
            )
        )

        return tools
