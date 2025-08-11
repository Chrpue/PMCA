from autogen_core.memory import MemoryContent, MemoryMimeType
from autogen_ext.memory.chromadb import (
    ChromaDBVectorMemory,
    HttpChromaDBVectorMemoryConfig,
)


# 远程 Chroma 服务地址及凭证（根据实际部署情况修改）
http_config = HttpChromaDBVectorMemoryConfig(
    client_type="http",
    host="localhost",  # ChromaDB Server 主机
    port=11003,  # HTTP 服务端口
    ssl=False,  # 是否启用 HTTPS
    # 以下为向量记忆专属参数：
    k=3,  # 查询时返回最相近的 top-k 条目
    score_threshold=0.5,  # 查询时返回结果的相似度阈值
    collection_name="decision_knowledge",
)

# 创建远程 Vector Memory 实例
chroma_memory = ChromaDBVectorMemory(config=http_config)


async def main():
    await chroma_memory.add(
        MemoryContent(
            content="用户任务：查看本地文件的内容，如报警记录、巡检记录等。选择组件：Swarm",
            mime_type=MemoryMimeType.TEXT,
            metadata={"role": "team_decision_agent", "scope": "decision_choice"},
        )
    )
    # await chroma_memory.add(
    #     MemoryContent(
    #         content="用户任务：对磨溪022-H26井进行电子巡检。选择组件：GraphFlow",
    #         mime_type=MemoryMimeType.TEXT,
    #         metadata={"role": "team_decision_agent", "scope": "decision_choice"},
    #     )
    # )
    # await chroma_memory.add(
    #     MemoryContent(
    #         content="用户任务：对磨溪022-H26井进行电子巡检。选择团队成员：PMCAInspector",
    #         mime_type=MemoryMimeType.TEXT,
    #         metadata={"role": "agents_decision_agent", "scope": "decision_choice"},
    #     )
    # )
    # await chroma_memory.add(
    #     MemoryContent(
    #         content="用户任务：对磨溪022-H27井进行电子巡检。选择团队成员：PMCAInspector",
    #         mime_type=MemoryMimeType.TEXT,
    #         metadata={"role": "agents_decision_agent", "scope": "decision_choice"},
    #     )
    # )
    response = await chroma_memory.query("查看某一给文件的内容")
    print(response)


if __name__ == "__main__":
    import asyncio
    from dotenv import load_dotenv

    load_dotenv()

    asyncio.run(main())
