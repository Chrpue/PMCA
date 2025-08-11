from typing import Iterator
import asyncio

from lightrag import QueryParam
from mcp_server.rag.lightrag_init import RAGinitializer


async def query(content: str) -> str | Iterator[str]:
    """
    @param area 数据库名称
           mode 检索模式("local", "global", "hybrid", "naive", "mix", "bypass")
    """

    rag_initializer = RAGinitializer(area="ir")
    rag = await rag_initializer.initialize()

    return rag.query(content, param=QueryParam(mode="global"))  # type: ignore


async def insert(area: str, file_path: str, ids: str) -> None:
    """
    @param area 存储PGSQL的数据库
           file_path 文本信息路径
    """
    rag_initializer = RAGinitializer(area=area)
    rag = await rag_initializer.initialize()

    rag.chunk_entity_relation_graph.embedding_func = rag.embedding_func  # type: ignore

    with open(file_path, "r", encoding="utf-8") as f:
        rag.insert(f.read(), ids=[ids])


if __name__ == "__main__":
    # asyncio.run(
    #     insert(
    #         "strategy",
    #         "/home/chrpue/projects/PMCA/mcp/rag/inputs/气藏气井异常分析判断.txt",
    #         "动态数据分析1",
    #     )
    # )

    print(
        asyncio.run(
            query(
                "strategy",
                "一级节流后压力和什么有关系，如果它出现异常应该怎么进行归因分析?",
                "global",
                "动态数据分析1",
            )
        )
    )
