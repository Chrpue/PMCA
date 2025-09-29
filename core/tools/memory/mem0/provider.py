from __future__ import annotations
from typing import Any, Dict, List, Optional
from autogen_core.tools import FunctionTool
from loguru import logger

from core.memory.factory.mem0 import PMCAMem0LocalService
from core.tools.factory import PMCAToolProvider


class PMCAMem0ToolsProvider(PMCAToolProvider):
    """
    mem0 工具箱（MCP 映射版）：
    - add_memory
    - search_memories
    - get_all_memories
    - update_memory
    - delete_memory
    - delete_all_memories
    - get_memory_stats
    """

    def for_assistant(self, assistant_name: str) -> List[FunctionTool]:
        tools: List[FunctionTool] = []

        # ---------- add_memory ----------
        async def add_memory(
            content: str,
            user_id: Optional[str] = None,
            metadata: Optional[Dict[str, Any]] = None,
        ) -> Dict[str, Any]:
            """
            向 mem0 写入一条记忆。
            参数:
              - content: 记忆文本
              - user_id: 可选，归属用户/主体
              - metadata: 可选，额外元数据(dict)
            返回: { ok, id, raw }
            """
            mem = PMCAMem0LocalService.memory(assistant_name)
            try:
                # ⭐ 若你的服务方法不同（例如 mem.add_text），替换此处
                res = await mem.add(content=content, user_id=user_id, metadata=metadata)
                # 常见返回可能含 { "id": "...", "content": "...", ... }
                memory_id = res.get("id") if isinstance(res, dict) else None
                return {"ok": True, "id": memory_id, "raw": res}
            except Exception as e:
                logger.exception("add_memory failed")
                return {"ok": False, "error": str(e)}

        tools.append(
            FunctionTool(name="add_memory", description="写入一条记忆", func=add_memory)
        )

        # ---------- search_memories ----------
        async def search_memories(
            query: str,
            user_id: Optional[str] = None,
            limit: int = 5,
            threshold: Optional[float] = None,
            filters: Optional[Dict[str, Any]] = None,
        ) -> Dict[str, Any]:
            """
            语义检索记忆。
            参数:
              - query: 查询文本
              - user_id: 可选，限定用户/主体
              - limit: 返回条数上限
              - threshold: 可选，相似度阈值（由具体实现决定）
              - filters: 可选，元数据过滤
            返回: { ok, items: [ {id, content, metadata, score, ...} ], raw }
            """
            mem = PMCAMem0LocalService.memory(assistant_name)
            try:
                # ⭐ 若你的服务方法不同（例如 mem.search_text），替换此处
                res = await mem.search(
                    query=query,
                    user_id=user_id,
                    limit=limit,
                    threshold=threshold,
                    filters=filters,
                )
                # 统一为 items 数组
                items = []
                if isinstance(res, dict) and "results" in res:
                    src = res["results"]
                else:
                    src = res
                for r in src or []:
                    # 容错提取
                    items.append(
                        {
                            "id": r.get("id") or r.get("_id"),
                            "content": r.get("content") or r.get("text"),
                            "metadata": r.get("metadata"),
                            "score": r.get("score"),
                        }
                    )
                return {"ok": True, "items": items, "raw": res}
            except Exception as e:
                logger.exception("search_memories failed")
                return {"ok": False, "error": str(e)}

        tools.append(
            FunctionTool(
                name="search_memories", description="语义检索记忆", func=search_memories
            )
        )

        # ---------- get_all_memories ----------
        async def get_all_memories(
            user_id: Optional[str] = None,
        ) -> Dict[str, Any]:
            """
            获取某主体（可选）下的所有记忆。
            返回: { ok, items, raw }
            """
            mem = PMCAMem0LocalService.memory(assistant_name)
            try:
                # ⭐ 如你的方法名是 list()/all() 请替换
                res = await mem.get_all(user_id=user_id)
                items = []
                for r in res or []:
                    items.append(
                        {
                            "id": r.get("id") or r.get("_id"),
                            "content": r.get("content") or r.get("text"),
                            "metadata": r.get("metadata"),
                            "created_at": r.get("created_at"),
                            "updated_at": r.get("updated_at"),
                        }
                    )
                return {"ok": True, "items": items, "raw": res}
            except Exception as e:
                logger.exception("get_all_memories failed")
                return {"ok": False, "error": str(e)}

        tools.append(
            FunctionTool(
                name="get_all_memories",
                description="获取全部记忆",
                func=get_all_memories,
            )
        )

        # ---------- update_memory ----------
        async def update_memory(
            memory_id: str,
            content: Optional[str] = None,
            metadata: Optional[Dict[str, Any]] = None,
        ) -> Dict[str, Any]:
            """
            更新一条记忆（内容与/或元数据）。
            注意：不同 mem0 版本字段名可能是 data={'content': ...} 或 data={'text': ...}
            返回: { ok, id, raw }
            """
            mem = PMCAMem0LocalService.memory(assistant_name)
            try:
                data: Dict[str, Any] = {}
                if content is not None:
                    # ⭐ 若你的底层要求 key= "text"，请在此切换
                    data["content"] = content
                if metadata is not None:
                    data["metadata"] = metadata
                # ⭐ 若你的方法签名不同（如 update(id, **data)），替换此处
                res = await mem.update(memory_id=memory_id, data=data)
                return {"ok": True, "id": memory_id, "raw": res}
            except Exception as e:
                logger.exception("update_memory failed")
                return {"ok": False, "error": str(e)}

        tools.append(
            FunctionTool(
                name="update_memory", description="更新指定记忆", func=update_memory
            )
        )

        # ---------- delete_memory ----------
        async def delete_memory(memory_id: str) -> Dict[str, Any]:
            """
            删除一条记忆。
            返回: { ok, id }
            """
            mem = PMCAMem0LocalService.memory(assistant_name)
            try:
                # ⭐ 若方法名不同（remove/delete_by_id），替换此处
                await mem.delete(memory_id=memory_id)
                return {"ok": True, "id": memory_id}
            except Exception as e:
                logger.exception("delete_memory failed")
                return {"ok": False, "error": str(e)}

        tools.append(
            FunctionTool(
                name="delete_memory", description="删除指定记忆", func=delete_memory
            )
        )

        # ---------- delete_all_memories ----------
        async def delete_all_memories(user_id: Optional[str] = None) -> Dict[str, Any]:
            """
            清空（某主体）的所有记忆。
            返回: { ok }
            """
            mem = PMCAMem0LocalService.memory(assistant_name)
            try:
                # ⭐ 若你的方法名是 clear()/truncate()，替换此处
                await mem.clear(user_id=user_id)
                return {"ok": True}
            except Exception as e:
                logger.exception("delete_all_memories failed")
                return {"ok": False, "error": str(e)}

        tools.append(
            FunctionTool(
                name="delete_all_memories",
                description="清空全部记忆",
                func=delete_all_memories,
            )
        )

        # ---------- get_memory_stats ----------
        async def get_memory_stats(user_id: Optional[str] = None) -> Dict[str, Any]:
            """
            获取记忆统计信息（数量、嵌入维度、向量库健康度等）
            返回: { ok, stats, raw }
            """
            mem = PMCAMem0LocalService.memory(assistant_name)
            try:
                # ⭐ 如果你的服务没有 stats，可自己封装：count()/ping()/dims 等
                res = await mem.stats(user_id=user_id)
                return {"ok": True, "stats": res, "raw": res}
            except Exception as e:
                logger.exception("get_memory_stats failed")
                return {"ok": False, "error": str(e)}

        tools.append(
            FunctionTool(
                name="get_memory_stats",
                description="获取记忆统计信息",
                func=get_memory_stats,
            )
        )

        return tools
