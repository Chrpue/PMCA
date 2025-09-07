import asyncio
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.ui import Console
from autogen_core.memory import MemoryContent, MemoryMimeType
from autogen_ext.memory.mem0 import Mem0Memory
from client import LLMFactory, ProviderType, DutyType
from core.memory.factory import PMCAMem0LocalService

# Initialize Mem0 cloud memory (requires API key)
# For local deployment, use is_cloud=False with appropriate config
mem0_memory = PMCAMem0LocalService.memory("pengbing")

model_client = LLMFactory.client(
    ProviderType.DEEPSEEK,
    DutyType.BASE,
)


async def main():
    # Add user preferences to memory
    # await mem0_memory.add(
    #     MemoryContent(
    #         content="我于2005年改名叫彭铄斌,在此之前叫彭冰",
    #         mime_type=MemoryMimeType.TEXT,
    #         metadata={"category": "preferences", "type": "units"},
    #     )
    # )
    #
    # await mem0_memory.add(
    #     MemoryContent(
    #         content="我毕业于西安交通大学",
    #         mime_type=MemoryMimeType.TEXT,
    #         metadata={"category": "preferences", "type": "dietary"},
    #     )
    # )

    # Create assistant with mem0 memory
    assistant_agent = AssistantAgent(
        name="assistant_agent",
        model_client=model_client,
        memory=[mem0_memory],
    )

    # Ask about the weather
    stream = assistant_agent.run_stream(
        task="我是谁?我的曾用名是什么？我毕业于哪个高校？"
    )
    await Console(stream)


if __name__ == "__main__":
    config_json = mem0_memory.dump_component().model_dump_json()
    print(f"Memory config JSON: {config_json[:100]}...")
    asyncio.run(main())
