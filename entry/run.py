import asyncio
from autogen_agentchat.ui import Console
from loguru import logger

from base.runtime.system_runtime import PMCARuntime
from entry.selector_group import build_selector_group


async def main():
    runtime = PMCARuntime()
    await runtime.initialize()

    # 你可以把 mission 文本通过 CLI/HTTP 传进来，这里先留空
    task_ctx = runtime.create_task_context(mission="")

    group = await build_selector_group(task_ctx)

    # 让 Planner 先开场：在实际实现里，Planner 会读 task_ctx.task_mission 并给出 steps 及 route_hint
    user_instruction = "请描述你的任务或需求。"
    logger.info("启动 SelectorGroupChat ...")
    await Console(group.run_stream(task=user_instruction))


if __name__ == "__main__":
    asyncio.run(main())
