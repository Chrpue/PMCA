import os
from pathlib import Path
from dotenv import load_dotenv

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.ui import Console
from autogen_core.memory import MemoryContent, MemoryMimeType
from autogen_ext.memory.chromadb import (
    ChromaDBVectorMemory,
    HttpChromaDBVectorMemoryConfig,
    PersistentChromaDBVectorMemoryConfig,
)
from autogen_ext.models.openai import OpenAIChatCompletionClient
from client.llm_client import LLMClient
from base.memory import PMCADecisionMemory


async def team_choice(scope: str = "file_choice") -> str:
    if scope == "file_choice":
        return "文件选择"
    elif scope == "team_choice":
        return "团队选择"
    else:
        return "Sorry, I don't know."


async def main():
    load_dotenv()
    # Initialize ChromaDB memory with custom config
    chroma_user_memory = PMCADecisionMemory()

    # a HttpChromaDBVectorMemoryConfig is also supported for connecting to a remote ChromaDB server

    # Add user preferences to memory
    await chroma_user_memory.add(
        MemoryContent(
            content="用户任务：H8井最近有没有发生异常情况。选择组件：GraphFlow",
            mime_type=MemoryMimeType.TEXT,
            metadata={"role": "pmca_decision_agent", "scope": "team_choice"},
        )
    )

    await chroma_user_memory.add(
        MemoryContent(
            content="用户任务：查询昨天的报警信息数量。选择组件：RoundRobin",
            mime_type=MemoryMimeType.TEXT,
            metadata={"role": "pmca_decision_agent", "scope": "team_choice"},
        )
    )

    await chroma_user_memory.add(
        MemoryContent(
            content="用户任务：打开电子巡检报表。文件类型：excel",
            mime_type=MemoryMimeType.TEXT,
            metadata={"role": "pmca_decision", "scope": "file_choice"},
        )
    )
    model_client = LLMClient.get_llm_client("qwen", "base")

    # Create assistant agent with ChromaDB memory
    assistant_agent = AssistantAgent(
        name="assistant_agent",
        model_client=model_client,
        tools=[team_choice],
        memory=[chroma_user_memory],
    )

    stream = assistant_agent.run_stream(
        task="查询今天上午8点的报警数量，这样的任务应该选择什么组件"
    )
    await Console(stream)

    await model_client.close()
    await chroma_user_memory.close()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
