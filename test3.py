import asyncio
from autogen_core import CancellationToken  # 假设这个类存在


# 模拟 PMCAUserProxy 中的输入函数
async def get_user_approval(prompt: str, token: CancellationToken):
    print(f"系统: {prompt}")
    print("系统: 正在等待用户确认，请在5秒内输入 (否则任务将被自动取消)...")

    # 同样使用 to_thread 来避免阻塞
    input_task = asyncio.create_task(asyncio.to_thread(input, "> "))

    # 将上层传来的 token 与当前输入任务链接
    token.link_future(input_task)

    try:
        user_input = await input_task
        print(f"用户输入了: '{user_input}'")
        return user_input
    except asyncio.CancelledError:
        print("\n系统: 等待输入的任务被外部取消了！")
        return "CANCELLED"


# 模拟一个更高层的任务管理器
async def run_long_task():
    print("任务管理器: 流程启动！")

    # 1. 在顶层创建 CancellationToken 实例
    main_token = CancellationToken()

    # 模拟一个 5 秒的超时取消器
    # 它会在 5 秒后调用 main_token.cancel()
    async def timeout_canceller():
        await asyncio.sleep(5)
        print("\n任务管理器: 5秒超时！正在触发全局取消...")
        main_token.cancel()

    # 启动超时取消器，它在后台运行
    asyncio.create_task(timeout_canceller())

    # 2. 将创建的 token 手动传入需要它的函数中
    result = await get_user_approval(prompt="是否批准执行该操作？", token=main_token)

    if result == "CANCELLED":
        print("任务管理器: 流程已终止。")
    else:
        print("任务管理器: 流程正常完成。")


# 运行主程序
if __name__ == "__main__":
    asyncio.run(run_long_task())
