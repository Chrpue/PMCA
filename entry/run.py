import asyncio
from autogen_agentchat.ui import Console
from loguru import logger

from base.configs import PMCASystemEnvConfig
from base.runtime import PMCARuntime
from core.team.engine import PMCASelectorGroup


async def main():
    runtime = PMCARuntime()
    await runtime.initialize()

    task_ctx = runtime.create_task_context(mission="请在这里输入您的任务...")

    group = PMCASelectorGroup(ctx=task_ctx)
    mas_team = group.build()

    if PMCASystemEnvConfig.INTERACTION_MODE == "console":
        logger.info("--- 系统运行在【控制台交互模式】---")
        await Console(mas_team.run_stream(task=task_ctx.task_mission))
    else:  # SERVICE 模式
        logger.info("--- 系统运行在【后台服务模式】---")
        # 直接运行，适合作为 API 的后端
        result = await mas_team.run(task=task_ctx.task_mission)
        logger.success("任务已完成。最终结果:")
        # 打印最终的消息内容
        if result.messages:
            print(result.messages[-1].content)

    logger.info("--- PMCA 任务执行完毕 ---")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("用户手动中断程序.")
