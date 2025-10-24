import asyncio
from autogen_agentchat.ui import Console
from loguru import logger

from base.runtime import PMCARuntime
from core.team.engine import PMCAFlowController
from base.runtime.event import TriageEvent, TriageSummaryEvent, AssistantStatusEvent


async def main():
    runtime = PMCARuntime()
    await runtime.initialize()

    # task_ctx = runtime.create_task_context()

    task_ctx = await runtime.create_task_context_with_blackboard(
        mission="",
        event_classes=[TriageEvent, TriageSummaryEvent, AssistantStatusEvent],
    )

    controller = PMCAFlowController(task_ctx)
    flow = await controller.overall_graph
    await Console(flow.run_stream())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("用户手动中断程序.")
