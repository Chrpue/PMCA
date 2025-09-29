from core.memory.factory.mem0 import PMCAMem0LocalService
import asyncio


async def smoke():
    await PMCAMem0LocalService.add_memory(
        "diagnostic_agent", "hello mem0 vector!", {"purpose": "smoke_test"}
    )
    res = await PMCAMem0LocalService.retrieve_memory(
        "diagnostic_agent", "hello", top_k=1
    )
    print(res)


asyncio.run(smoke())
