import asyncio
from autogen_core.memory import MemoryContent, MemoryMimeType
from base.runtime import PMCARuntime
from core.memory.factory.mem0 import PMCAMem0LocalService
from loguru import logger


async def test_mem0_with_graph_content():
    logger.info("--- 启动 mem0 知识图谱功能测试 ---")

    runtime = PMCARuntime()
    await runtime.initialize()
    logger.success("PMCARuntime 初始化完成。")

    agent_name = "KnowledgeGraphTester"  # 使用一个新的 agent 名以保持隔离
    mem = PMCAMem0LocalService.memory(agent_name)

    # --- 使用一段信息更丰富的内容 ---
    knowledge_rich_content = (
        "AutoGen is a framework from Microsoft that enables the development of LLM applications "
        "using multiple agents. These agents can converse with each other to solve tasks."
    )

    try:
        logger.info(f"正在为 '{agent_name}' 添加知识密集型记忆...")
        content = MemoryContent(
            content=knowledge_rich_content,
            mime_type=MemoryMimeType.TEXT,
            metadata={"source": "graph_test"},
        )
        await mem.add(content)
        logger.success("记忆添加成功！请检查 Neo4j 的日志和浏览器。")

    except Exception as e:
        logger.error(f"在 'add' 操作中捕获到异常: {e}")
        # 如果这里还报错，可能就是连接问题了
        logger.error(
            "如果看到此错误，请检查您的防火墙或确认 `localhost:27687` 是否可达。"
        )
        return

    finally:
        # 为了方便您在 Neo4j 浏览器中查看，我们暂时不清除这次的记忆
        logger.info(
            "测试结束。您可以打开 Neo4j Browser (http://localhost:27474) 查看是否生成了图谱。"
        )
        logger.info("用户名: neo4j, 密码: mem0graph")


if __name__ == "__main__":
    # 建议在运行前删除可能存在的旧表
    # psql -U postgres -c "DROP TABLE IF EXISTS knowledge_graph_tester;"
    asyncio.run(test_mem0_with_graph_content())
