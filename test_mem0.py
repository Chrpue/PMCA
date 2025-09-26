import asyncio
from base.runtime import PMCARuntime
from core.memory.factory.mem0 import PMCAMem0LocalService
from autogen_core.memory import MemoryContent, MemoryMimeType


async def test_mem0():
    runtime = PMCARuntime()
    await runtime.initialize()

    agent_name = "test_001"
    mem = PMCAMem0LocalService.memory(agent_name)

    # 构造 MemoryContent 对象并添加到 mem0
    # content1 = MemoryContent(
    #     content="张曦予的爸爸是张彦川",
    #     mime_type=MemoryMimeType.TEXT,
    #     metadata={"purpose": "connectivity_test"},
    # )
    # await mem.add(content1)
    #
    # content2 = MemoryContent(
    #     content="张曦予的生日是1988年02月06日，她于2016年07月08日不再是单身",
    #     mime_type=MemoryMimeType.TEXT,
    #     metadata={"purpose": "connectivity_test"},
    # )
    # await mem.add(content2)
    #
    # content3 = MemoryContent(
    #     content="彭冰的老婆是张曦予",
    #     mime_type=MemoryMimeType.TEXT,
    #     metadata={"purpose": "connectivity_test"},
    # )
    # await mem.add(content3)

    # content = MemoryContent(
    #     content="彭冰的女儿是彭朴，彭冰目前只结过一次婚",
    #     mime_type=MemoryMimeType.TEXT,
    #     metadata={"purpose": "connectivity_test"},
    # )
    # await mem.add(content)
    # 查询并打印结果
    result = await mem.query("张彦川的外孙女是谁", limit=5)
    print(f"Got {len(result.results)} results: {result.results}")

    # 清空内存
    # await mem.clear()


if __name__ == "__main__":
    asyncio.run(test_mem0())
