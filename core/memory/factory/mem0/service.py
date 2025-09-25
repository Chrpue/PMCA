"""
An enhanced version of the PMCA mem0 memory service.

This module provides a convenience wrapper around the underlying
``autogen_ext.memory.mem0.Mem0Memory`` class used in the PMCA project.  It adds
simple caching, metadata‑aware operations and more expressive method names to
make working with mem0 memory instances easier and more Pythonic.

Key features:

1. **Instance caching**: A mem0 memory instance is created once per agent and
   reused across subsequent calls, saving the overhead of repeatedly
   constructing the object.  Instances are isolated by agent name.

2. **Add, retrieve and clear operations**: High‑level methods are provided to
   add memory entries, retrieve memories via semantic search, and clear
   memories (either selectively or wholesale).  These wrap the underlying
   ``add``, ``search`` and ``delete`` methods and accept optional
   ``metadata`` filters to support fine‑grained memory isolation.

3. **Metadata support**: All add/retrieve/clear operations accept
   arbitrary metadata dictionaries.  When adding memory, the metadata is
   stored alongside the content and can later be used to filter retrieval
   or deletion operations.  When retrieving or clearing, the metadata
   filter is passed through to the underlying mem0 implementation.

This service is intended to be used wherever the original
``PMCAMem0LocalService`` was used, but adds additional functionality
requested by the user.  If you integrate it into your project, you
may replace your existing service or adapt its methods accordingly.

NOTE: This module does not mutate any existing repository code.  It
serves as a self‑contained example of how to enhance the mem0 service.
"""

import re
import copy
import asyncio
from typing import Any, Dict, List, Optional

from loguru import logger

try:
    from autogen_ext.memory.mem0 import Mem0Memory

    from base.configs import PMCAMem0LocalConfig
    from autogen_core.memory import MemoryContent, MemoryMimeType
except ImportError as e:
    raise ImportError(
        f"依赖导入失败: {e}。请确保 'autogen-ext[mem0-local]' 已安装，"
        "并且 base.memory.configs.PMCAMem0LocalConfig 路径正确。"
    ) from e


class PMCAMem0LocalService:
    """
    A convenience layer around ``Mem0Memory`` with caching and metadata support.

    This class exposes synchronous methods that internally drive the asynchronous
    ``Mem0Memory`` API.  Each operation spins up a new event loop (or reuses
    the existing one) to call the underlying coroutine.  This design makes
    the service easier to use from synchronous contexts (e.g. within threads).
    """

    _mem0_config: Dict[str, Any] = PMCAMem0LocalConfig
    _instances: Dict[str, Mem0Memory] = {}

    @staticmethod
    def _agent_to_collection(agent_name: str) -> str:
        return re.sub(
            r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", "_", agent_name
        ).lower()

    @classmethod
    def _get_instance(cls, agent_name: str) -> Mem0Memory:
        """
        Lazily construct and cache a Mem0Memory instance for a given agent.

        Args:
            agent_name: The unique identifier for the agent, used as the mem0
                ``user_id``.  Separate names map to isolated memory stores.

        Returns:
            A ``Mem0Memory`` instance configured for local storage.
        """
        if agent_name not in cls._instances:
            # 深拷贝基础配置并覆盖 collection_name
            config = copy.deepcopy(cls._mem0_config)
            collection = cls._agent_to_collection(agent_name)
            vector_cfg = config.setdefault("vector_store", {}).setdefault("config", {})
            vector_cfg["collection_name"] = collection
            logger.info(
                f"Creating new mem0 instance for '{agent_name}', collection='{collection}'"
            )
            cls._instances[agent_name] = Mem0Memory(
                user_id=collection, is_cloud=False, config=config
            )
        return cls._instances[agent_name]

    @classmethod
    def memory(cls, agent_name: str) -> Mem0Memory:
        """Return a raw ``Mem0Memory`` instance for direct use with autogen."""
        return cls._get_instance(agent_name)

    @classmethod
    async def add_memory(
        cls,
        agent_name: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Add a single textual memory entry for a given agent.

        This is a synchronous wrapper around the asynchronous ``Mem0Memory.add``
        coroutine.  It constructs a ``MemoryContent`` object and uses
        ``asyncio.run`` to await the underlying call.

        Args:
            agent_name: The agent whose memory should be updated.
            content: The text content to store.  This may include newlines
                and arbitrary length text; internally it will be treated as
                a single ``MemoryContent`` record.
            metadata: An optional dictionary of metadata key/value pairs to
                associate with this memory entry.  These keys can later be
                used to filter retrieval or clear operations.

        The content is stored with ``MemoryMimeType.TEXT``.  If you need
        other MIME types (e.g. code or binary), adjust this accordingly.
        """
        instance = cls._get_instance(agent_name)
        mem = MemoryContent(
            content=content,
            mime_type="text/plain",
            metadata=metadata or {},
        )
        logger.debug(
            f"Adding memory for agent '{agent_name}' with metadata {metadata or {}}"
        )

        await instance.add(mem)

    @classmethod
    async def retrieve_memory(
        cls,
        agent_name: str,
        query: str,
        top_k: int = 5,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> List[Any]:
        """
        Retrieve relevant memory entries using a natural language query.

        This wrapper calls the asynchronous ``Mem0Memory.query`` coroutine via
        ``asyncio.run``.  Additional keyword arguments are passed through to
        the underlying mem0 search implementation; in particular, a
        ``metadata_filter`` can be supplied to restrict results to entries
        matching specific metadata keys/values (if supported by the mem0 API).

        Args:
            agent_name: The agent whose memory to search.
            query: A natural language query.
            top_k: The maximum number of results to return.
            metadata_filter: Optional metadata constraints.  Only entries
                whose metadata matches all key/value pairs in this filter
                will be considered.

        Returns:
            A list of ``MemoryContent`` objects representing the search
            results.  If the underlying API does not support metadata
            filtering, the filter will be ignored.
        """
        instance = cls._get_instance(agent_name)
        logger.debug(
            f"Searching memory for agent '{agent_name}' with query='{query}', top_k={top_k}, "
            f"metadata_filter={metadata_filter}"
        )

        kwargs = {}
        if metadata_filter:
            kwargs["metadata_filter"] = metadata_filter

        result = await instance.query(query, limit=top_k, **kwargs)
        return result.results

    @classmethod
    async def clear_memory(
        cls,
        agent_name: str,
        ids: Optional[List[str]] = None,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Delete memory entries for a given agent.

        This wrapper provides three behaviours:

        * When no ``ids`` or ``metadata_filter`` are supplied, it calls
          ``Mem0Memory.clear`` to erase all memories for the agent.
        * When either ``ids`` or ``metadata_filter`` is supplied, it accesses
          the underlying mem0 client's ``delete`` method to remove matching
          records.  Note that this feature depends on internal API
          availability and may not be supported by all mem0 backends.
        * It is an error to provide both ``ids`` and ``metadata_filter``.

        Args:
            agent_name: The agent whose memory to purge.
            ids: Optional list of memory IDs to delete.
            metadata_filter: Optional dictionary specifying metadata
                constraints.

        Returns:
            The number of records deleted, or 0 if unsupported.
        """
        """
        为一个给定的智能体异步地删除记忆条目。
        """
        instance = cls._get_instance(agent_name)

        if ids is None and metadata_filter is None:
            logger.debug(f"删除智能体 '{agent_name}' 的 *所有* 记忆...")
            await instance.clear()
            return 0

        if ids is not None and metadata_filter is not None:
            raise ValueError("清除记忆时不能同时指定 'ids' 和 'metadata_filter'。")

        logger.debug(
            f"为智能体 '{agent_name}' 删除记忆，ids={ids} metadata_filter={metadata_filter}"
        )

        client = getattr(instance, "_client", None)
        if client is None:
            logger.warning("无法访问底层的 mem0 客户端；无法执行选择性删除。")
            return 0

        try:
            # 假设底层的 delete 方法也是异步的
            if ids is not None:
                await client.delete(ids=ids, user_id=agent_name)
            elif metadata_filter is not None:
                await client.delete(metadata_filter=metadata_filter, user_id=agent_name)
            return 0  # 底层 API 可能不返回计数
        except Exception as e:
            # 检查 delete 方法是否可等待
            if "is not awaitable" in str(e):
                logger.warning("底层的 mem0 delete 方法可能不是异步的。尝试同步调用。")
                if ids is not None:
                    client.delete(ids=ids, user_id=agent_name)
                elif metadata_filter is not None:
                    client.delete(metadata_filter=metadata_filter, user_id=agent_name)
                return 0
            logger.error(f"删除 mem0 记忆时出错: {e}")
            return 0

    @classmethod
    async def shutdown(cls):
        """
        优雅地关闭所有缓存的 Mem0Memory 实例。
        这个最终版本会深入实例内部，找到真正的数据库客户端并关闭它们。
        """
        logger.info(f"开始关闭所有 {len(cls._instances)} 个 mem0 实例和数据库连接...")

        if not cls._instances:
            logger.warning(
                "PMCAMem0LocalService._instances 字典为空，没有实例可以关闭。"
            )
            return

        async_close_tasks = []

        for agent_name, instance in cls._instances.items():
            logger.debug(f"正在处理 agent '{agent_name}' 的实例...")

            # autogen 的包装器是 'instance'
            # mem0 的核心对象是 'instance._client'
            mem0_core_object = getattr(instance, "_client", None)

            if not mem0_core_object:
                logger.warning(f"Agent '{agent_name}' 的实例没有找到 _client 属性。")
                continue

            # --- 核心修正：深入核心对象内部，寻找真正的数据库存储客户端 ---
            # 向量数据库客户端通常存储在 'vector_store' 属性里
            vector_store_client = getattr(mem0_core_object, "vector_store", None)

            if (
                vector_store_client
                and hasattr(vector_store_client, "close")
                and callable(vector_store_client.close)
            ):
                # 假设 close 是异步的，这对于数据库客户端是很常见的
                if asyncio.iscoroutinefunction(vector_store_client.close):
                    logger.debug(
                        f"发现 agent '{agent_name}' 的 vector_store 有异步 close 方法，添加到任务列表。"
                    )
                    async_close_tasks.append(vector_store_client.close())
                else:
                    # 如果是同步的，就在线程中运行
                    logger.debug(
                        f"发现 agent '{agent_name}' 的 vector_store 有同步 close 方法，在线程中执行。"
                    )
                    try:
                        await asyncio.to_thread(vector_store_client.close)
                    except Exception as e:
                        logger.error(f"调用同步 close 方法时出错: {e}")
            else:
                logger.warning(
                    f"Agent '{agent_name}' 的 vector_store 没有找到可调用的 'close' 方法。"
                )

        # 并发执行所有找到的异步关闭任务
        if async_close_tasks:
            await asyncio.gather(*async_close_tasks)
            logger.success("所有异步 mem0 客户端已成功关闭。")
        else:
            logger.warning("在所有实例中均未找到可关闭的异步客户端。")

        cls._instances.clear()
        logger.info("实例缓存已清空。")
