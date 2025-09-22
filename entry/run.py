import asyncio
from autogen_agentchat.ui import Console
from loguru import logger

from base.configs import PMCASystemEnvConfig
from base.runtime import PMCARuntime
from core.team.engine import PMCAFlowController


async def main():
    runtime = PMCARuntime()
    await runtime.initialize()

    task_ctx = runtime.create_task_context()

    controller = PMCAFlowController(task_ctx)
    flow = await controller.overall_graph
    await Console(flow.run_stream())

    # group = PMCARoundRobin(ctx=task_ctx)

    # await group.run_chat(background=False)

    # await result


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("用户手动中断程序.")
