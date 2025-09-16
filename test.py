import asyncio
from loguru import logger
import sys

# 确保脚本可以找到您的核心模块
sys.path.append(".")

from autogen_agentchat.base import Team
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import MaxMessageTermination
from autogen_agentchat.agents import AssistantAgent

from base.runtime import PMCARuntime, PMCATaskContext
from core.team.engine import PMCATeamBase
from core.team.common import PMCARoutingMessages

# 【核心修正】直接导入您已经写好的 PMCAUserProxy
from core.team.core_assistants.user_proxy import PMCAUserProxy


# 1. 创建一个能够触发用户中断的、更真实的测试团队
class InteractiveTestTeam(PMCATeamBase):
    """
    一个用于测试中断、暂停、保存、恢复逻辑的交互式团队。
    """

    def build(self) -> Team:
        """
        构建一个包含分析师和您的 PMCAUserProxy 的 RoundRobinGroupChat 团队。
        """
        # Analyst Agent: 它被设定为在没有得到具体指令时，会向用户提问
        analyst_agent = AssistantAgent(
            name="Analyst_Agent",
            system_message=f"""你是一名分析师。你的任务是分析数据。
如果用户没有提供明确的数据来源，你必须向用户提问：“我需要知道要分析哪个文件，请提供文件路径。”
在你的提问之后，你必须紧接着输出中断信号：`{PMCARoutingMessages.TEAM_NEED_USER.value}`。
如果用户提供了文件路径，你就回复：“收到，正在分析文件：[文件路径]。分析完成。”
""",
            model_client=self._ctx.llm_factory.client(),
        )

        # 【核心修正】使用您代码中现成的 PMCAUserProxy
        # 我们不再使用 AutoGen 默认的 UserProxyAgent
        user_proxy = PMCAUserProxy().build_user_proxy_assistant()

        return RoundRobinGroupChat(
            name="InteractiveRoundRobinTeam",
            participants=[analyst_agent, user_proxy],
            termination_condition=MaxMessageTermination(max_messages=5),
        )


async def main():
    """
    测试的主函数，完整演示“启动 -> 中断 -> 恢复 -> 完成”的流程。
    """
    logger.info("--- 开始测试 PMCATeamBase 的中断与恢复逻辑 ---")

    # --- 环境初始化 ---
    runtime = PMCARuntime()
    await runtime.initialize()
    task_ctx = runtime.create_task_context(mission="交互式分析任务")

    # 【重要】确保 .env 中 INTERACTION_MODE=service
    # if task_ctx.task_env.INTERACTION_MODE != "service":
    #     logger.error(
    #         "本次测试必须在 service 模式下运行，请在 .env 文件中设置 INTERACTION_MODE=service"
    #     )
    #     return

    # --- 实例化团队 ---
    test_team = InteractiveTestTeam(ctx=task_ctx)
    team_name = test_team.team.name
    state_key = f"team_state_{team_name}"

    # --- 阶段一: 启动任务并触发中断 ---
    logger.info(f"--- 阶段一：启动 '{team_name}' 并预期它会请求用户输入 ---")
    initial_task = "请帮我分析数据"

    response_from_analyst = await test_team.start(initial_task)

    print("\n" + "=" * 20 + " 阶段一结果 " + "=" * 20)
    print(f"团队返回的信息: {response_from_analyst}")
    print("=" * 52 + "\n")

    if PMCARoutingMessages.TEAM_NEED_USER.value in response_from_analyst:
        logger.error("测试失败：团队返回了信号，而不是具体问题。")
        return
    else:
        logger.success("阶段一成功：团队已暂停，并返回了需要用户回答的问题。")

    # --- 阶段二: 模拟用户回复并恢复团队 ---
    logger.info(f"--- 阶段二：模拟用户提供信息，并恢复团队 '{team_name}' ---")

    user_response = "/home/data/log.csv"
    logger.info(f"模拟用户输入: {user_response}")

    # 重新创建一个团队实例来模拟一个新的请求流程
    resumed_test_team = InteractiveTestTeam(ctx=task_ctx)

    saved_state = await task_ctx.task_workbench.get_item(state_key)
    if not saved_state:
        logger.error("测试失败：未能从工作台加载已保存的团队状态。")
        return

    await resumed_test_team.team.load_state(saved_state)
    await resumed_test_team.resume()

    final_result = await resumed_test_team.start(user_response)

    # --- 打印最终结果 ---
    logger.success("--- 测试完成 ---")
    print("\n" + "=" * 20 + " 最终结果 " + "=" * 20)
    print(final_result)
    print("=" * 52)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"测试过程中发生错误: {e}", exc_info=True)

