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

from typing import Any, Dict, List, Optional

from loguru import logger

try:
    from autogen_ext.memory.mem0 import Mem0Memory

    from base.memory.configs import PMCAMem0LocalConfig
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
            logger.info(
                f"Creating new mem0 memory instance for agent '{agent_name}'..."
            )
            instance = Mem0Memory(
                user_id=agent_name,
                is_cloud=False,
                config={**cls._mem0_config},
            )
            cls._instances[agent_name] = instance
        return cls._instances[agent_name]

    @classmethod
    def memory(cls, agent_name: str) -> Mem0Memory:
        """Return a raw ``Mem0Memory`` instance for direct use with autogen."""
        return cls._get_instance(agent_name)

    @classmethod
    def add_memory(
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
        import asyncio

        # Use a fresh event loop for the asynchronous add operation
        def _run_add():
            return instance.add(mem)  # type: ignore

        # Run the coroutine synchronously
        asyncio.run(_run_add())

    @classmethod
    def retrieve_memory(
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
        import asyncio

        async def _query():
            # Pass through metadata_filter via kwargs; mem0 may ignore unknown keys
            kwargs = {}
            if metadata_filter:
                kwargs["metadata_filter"] = metadata_filter
            return await instance.query(query, limit=top_k, **kwargs)  # type: ignore

        result = asyncio.run(_query())
        # ``query`` returns a MemoryQueryResult; extract list of MemoryContent
        return result.results  # type: ignore

    @classmethod
    def clear_memory(
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
        instance = cls._get_instance(agent_name)
        import asyncio

        if ids is None and metadata_filter is None:
            logger.debug(f"Deleting *all* memory for agent '{agent_name}'...")

            async def _clear_all():
                await instance.clear()  # type: ignore
                return 0

            return asyncio.run(_clear_all())
        if ids is not None and metadata_filter is not None:
            raise ValueError(
                "Cannot specify both 'ids' and 'metadata_filter' when clearing memory."
            )
        logger.debug(
            f"Deleting memory for agent '{agent_name}' with ids={ids} metadata_filter={metadata_filter}"
        )
        # Access internal client to perform fine‑grained deletions
        client = getattr(instance, "_client", None)
        if client is None:
            logger.warning(
                "Underlying mem0 client is not accessible; cannot delete selectively."
            )
            return 0

        async def _delete():
            try:
                # Some clients require keyword names to match; we try both
                if ids is not None:
                    return client.delete(ids=ids, user_id=agent_name)  # type: ignore
                if metadata_filter is not None:
                    return client.delete(
                        metadata_filter=metadata_filter, user_id=agent_name
                    )  # type: ignore
                return 0
            except Exception as e:
                logger.error(f"Error deleting mem0 memory: {e}")
                return 0

        # Running the underlying deletion synchronously (delete may be sync)
        return asyncio.run(_delete())
