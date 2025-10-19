from autogen_agentchat.agents import UserProxyAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from core.assistant.factory.assistant_factory import PMCAAssistantFactory


import asyncio
from autogen_agentchat.ui import Console
from loguru import logger

from base.configs import PMCASystemEnvConfig
from base.runtime import PMCARuntime
from core.team.engine import PMCAFlowController
from core.tools.factory.tool_registry import PMCAToolRegistry
from core.tools.memory.mem0.provider import PMCAMem0ToolsProvider


async def main():
    runtime = PMCARuntime()
    await runtime.initialize()
    task_ctx = runtime.create_task_context()

    # registry = PMCAToolRegistry()
    # mem0_tools_provider = PMCAMem0ToolsProvider()
    # registry.register_for_assistant("PMCAMasterOfMemory", mem0_tools_provider)
    orchestrator = task_ctx.assistant_factory.create_assistant("PMCAOrchestrator")
    # master_of_memory = task_ctx.assistant_factory.create_assistant("PMCAMasterOfMemory")
    # knowledge_strategist = task_ctx.assistant_factory.create_assistant(
    # "PMCAKnowledgeStrategist"
    # )
    knowledge_librarian = task_ctx.assistant_factory.create_assistant(
        "PMCAKnowledgeLibrarian"
    )
    # knowledge_technician = task_ctx.assistant_factory.create_assistant(
    # "PMCAKnowledgeTechnician"
    # )

    user_proxy = UserProxyAgent("user_proxy", input_func=input)

    team = RoundRobinGroupChat(
        [
            user_proxy,
            knowledge_librarian,
            # orchestrator,
        ]
    )

    await Console(team.run_stream(task=""))


if __name__ == "__main__":
    asyncio.run(main())
