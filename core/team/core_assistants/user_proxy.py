import asyncio
from typing import Optional, Callable, Awaitable

from autogen_agentchat.agents import UserProxyAgent
from autogen_core import CancellationToken

from base.configs import PMCASystemEnvConfig
from core.team.common import PMCARoutingMessages


class PMCAUserProxy:
    """封装 AutoGen UserProxyAgent 的用户代理。

    根据 ``PMCASystemEnvConfig.INTERACTION_MODE`` 选择不同的输入逻辑，以适配
    交互式命令行模式或服务化模式。
    """

    def __init__(self, name: str = "PMCAUserProxy") -> None:
        self._name = name
        self._description = (
            "一个用户代理，负责处理所有需要人类介入的场景，包括回答问题和发送控制指令。"
        )
        self._duty = """
     1. 在被动请求时提供信息或决策。
     2. 在任何需要输入时，主动发出控制指令（暂停、取消、中断）。"""

    async def _console_input_logic(
        self, prompt: str, cancellation_token: Optional[CancellationToken]
    ) -> str:
        """在控制台模式下，从终端读取用户输入。"""
        print("\n" + "=" * 50)
        print(" [用户介入点]")
        print(f"   系统提示: {prompt.strip()}")
        print("   您可以直接输入内容进行回复，或使用以下主动干预指令:")
        print("     - /cancel: 彻底取消并终止当前任务。")
        print("     - /pause:  暂停当前任务（上层协调器需实现状态保存逻辑）。")
        print(
            "     - /interrupt <新的指令或信息>: 中断当前执行方向，并提供新的上下文。"
        )
        print("=" * 50)

        input_task = asyncio.create_task(asyncio.to_thread(input, "您的输入 > "))

        if cancellation_token:
            cancellation_token.link_future(input_task)

        try:
            user_input = await input_task
        except asyncio.CancelledError:
            return PMCARoutingMessages.SIGNAL_CANCEL.value

        user_input = (user_input or "").strip()
        lower_input = user_input.lower()

        if lower_input == "/cancel":
            return PMCARoutingMessages.SIGNAL_CANCEL.value
        if lower_input == "/pause":
            return PMCARoutingMessages.SIGNAL_PAUSE.value
        if lower_input.startswith("/interrupt"):
            parts = user_input.split(" ", 1)
            if len(parts) > 1 and parts[1].strip():
                new_info = parts[1].strip()
                return f"{PMCARoutingMessages.SIGNAL_INTERRUPT_PREFIX.value} {new_info}"
            else:
                print("[中断] 指令格式错误，需要附加信息。本次输入将作为普通文本处理。")
                return user_input

        return user_input

    async def _service_input_logic(
        self, prompt: str, cancellation_token: Optional[CancellationToken]
    ) -> str:
        """在服务模式下，不阻塞等待用户输入，直接返回请求信号。"""
        # 这个函数虽然是异步的，但它会立即返回。
        return PMCARoutingMessages.TEAM_NEED_USER.value

    # 【核心修正】移除 async 和 await，直接返回函数对象
    def _choose_input_func(
        self,
    ) -> Callable[[str, Optional[CancellationToken]], Awaitable[str]]:
        """根据交互模式选择合适的输入函数。"""
        mode = PMCASystemEnvConfig.INTERACTION_MODE
        if mode == "console":
            return self._console_input_logic
        # 默认为服务模式
        return self._service_input_logic

    # 【核心修正】此方法为同步方法
    def build_user_proxy_assistant(self) -> UserProxyAgent:
        """构建并返回一个配置好输入逻辑的 UserProxyAgent。"""
        input_func = self._choose_input_func()
        return UserProxyAgent(
            name=self._name,
            description=self._description,
            input_func=input_func,
        )

