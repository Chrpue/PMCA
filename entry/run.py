import asyncio
from autogen_agentchat.ui import Console
from loguru import logger

from base.configs import PMCASystemEnvConfig
from base.runtime import PMCARuntime
from core.team.engine import PMCARoundRobin


async def main():
    runtime = PMCARuntime()
    await runtime.initialize()

    task_ctx = runtime.create_task_context(mission="请在这里输入您的任务...")

    group = PMCARoundRobin(ctx=task_ctx)

    task = await group.run_auto(background=True)

    result = await task


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("用户手动中断程序.")
