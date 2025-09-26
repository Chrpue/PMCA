# distill_cli.py

import argparse
import asyncio

from loguru import logger

# 导入我们刚刚创建的记忆服务
from core.memory.factory.mem0 import PMCAMem0LocalService

# --- 固定的知识蒸馏内容 ---
# 在真实场景中，这些内容会由 LLM 生成
DISTILLED_KNOWLEDGE = {
    "PMCATriage": (
        "我的核心身份是一个初步诊断和分诊AI。我必须遵守的核心原则是：快速、准确地评估用户请求的紧急性和类型。"
        "我需要记住的关键经验是：对于任何提及‘紧急’、‘立即’或‘危险’的词语，都应提高优先级。"
    ),
    "PMCADecision": (
        "我的核心身份是一个决策AI，负责根据分诊结果制定行动计划。我必须遵守的核心原则是：逻辑清晰、方案可行。"
        "我需要掌握的标准操作流程是：分析输入 -> 评估选项 -> 推荐最佳方案 -> 请求人类批准。"
    ),
}


async def inject_memory_for_agent(agent_name: str, knowledge_text: str):
    """
    一个封装了为单个智能体注入记忆的协程。
    """
    logger.info(f"--> Starting injection for agent: {agent_name}")
    try:
        await PMCAMem0LocalService.add_memory(
            agent_name=agent_name,
            content=knowledge_text,
            metadata={"source": "distillation_v2_test", "category": "core_identity"},
        )
    except Exception as e:
        logger.error(f"Injection failed for agent '{agent_name}': {e}")


async def main(agents_to_process: list[str]):
    """
    脚本主入口点。
    """
    logger.info("Starting knowledge distillation and memory injection test.")

    tasks = []
    for agent_name in agents_to_process:
        if knowledge := DISTILLED_KNOWLEDGE.get(agent_name):
            # 为每个需要处理的智能体创建一个异步任务
            task = inject_memory_for_agent(agent_name, knowledge)
            tasks.append(task)
        else:
            logger.warning(f"No knowledge defined for agent '{agent_name}'. Skipping.")

    if not tasks:
        logger.error("No valid agents to process. Exiting.")
        return

    # 并发执行所有记忆注入任务
    await asyncio.gather(*tasks)

    logger.info("All memory injection tasks have been submitted.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test script for memory injection.")
    parser.add_argument(
        "-a",
        "--agent",
        nargs="+",
        default=["PMCATriage", "PMCADecision"],
        help="List of agent names to process (e.g., -a PMCATriage PMCADecision). Default is all.",
    )
    args = parser.parse_args()

    loop = asyncio.get_event_loop()
    try:
        # 运行主逻辑
        loop.run_until_complete(main(args.agent))
    finally:
        # 关键：在程序结束前，给予一个“优雅期”让后台I/O任务完成
        logger.info(
            "Entering grace period (3 seconds) for background I/O to complete..."
        )
        loop.run_until_complete(asyncio.sleep(3))

        # 关闭服务
        PMCAMem0LocalService.shutdown()
        logger.info("Script finished.")

