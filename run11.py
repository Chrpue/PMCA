import numpy as np
import pandas as pd
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.conditions import TextMentionTermination
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.ui import Console
from autogen_ext.tools.mcp import SseServerParams, McpWorkbench

from client import LLMFactory, ProviderType, DutyType

llm_client = LLMFactory.client(ProviderType.QWEN, DutyType.BASE)


async def main():
    memory_server_params = SseServerParams(url="http://localhost:11005/sse", timeout=20)
    async with McpWorkbench(memory_server_params) as mcp:
        agent = AssistantAgent(
            "web_browsing_assistant",
            model_client=llm_client,
            workbench=[mcp],
            model_client_stream=True,
            system_message="你是一个文件助手，调用你的工具实现用户任务，你操作的目录有且仅有是/data",
        )
        team = RoundRobinGroupChat([agent], TextMentionTermination("TERMINATE"))
        await Console(team.run_stream(task=f"列出本地所有文件"))


if __name__ == "__main__":
    import asyncio
    from dotenv import load_dotenv

    load_dotenv()

    asyncio.run(main())
