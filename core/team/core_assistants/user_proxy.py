import asyncio
from typing import Optional

from autogen_agentchat.agents import UserProxyAgent
from autogen_core import CancellationToken

from core.team.common import PMCARoutingMessages


class PMCAUserProxy:
    """
    一个功能增强的用户代理，负责处理与人类用户的所有交互。

    该类通过一个自定义的输入函数，实现了用户的“被动介入”（回答系统提问）
    和“主动介入”（在任何需要输入的时刻发送控制命令）的能力。
    """

    SIGNAL_CANCEL = "[USER_CANCEL]"
    SIGNAL_CANCEL = PMCARoutingMessages.SIGNAL_CANCEL
    SIGNAL_PAUSE = "[USER_PAUSE]"
    SIGNAL_INTERRUPT_PREFIX = "[USER_INTERRUPT]"

    def __init__(self, name: str = "PMCAUserProxy"):
        """
        初始化用户代理包装类。
        Args:
            name (str): 代理的名称。
        """
        self._name = name
        self._description = (
            "一个用户代理，负责处理所有需要人类介入的场景，包括回答问题和发送控制指令。"
        )
        self._chinese_name = "用户代理"
        self._duty = "1. 在被动请求时提供信息或决策。 2. 在任何需要输入时，主动发出控制指令（暂停、取消、中断）。"

    async def _custom_input_logic(
        self, prompt: str, cancellation_token: Optional[CancellationToken]
    ) -> str:
        """
        自定义的输入逻辑，是实现主动/被动介入的核心。
        """
        print("\n" + "=" * 50)
        print("👤 [用户介入点]")
        # 打印系统给出的原始提示，让用户知道AI在请求什么
        print(f"   系统提示: {prompt.strip()}")
        print("   您可以直接输入内容进行回复，或使用以下主动干预指令:")
        print("     - /cancel: 彻底取消并终止当前任务。")
        print("     - /pause:  暂停当前任务（上层协调器需实现状态保存逻辑）。")
        print(
            "     - /interrupt <新的指令或信息>: 中断当前执行方向，并提供新的上下文。"
        )
        print("=" * 50)

        # 使用 asyncio.to_thread 在后台线程中运行阻塞的 input() 函数，避免阻塞事件循环
        # 这也是 UserProxyAgent 源码中的标准做法
        input_task = asyncio.create_task(asyncio.to_thread(input, "您的输入 > "))

        # 链接取消令牌，如果外部任务被取消，这个输入任务也会被取消
        if cancellation_token:
            cancellation_token.link_future(input_task)

        try:
            user_input = await input_task
        except asyncio.CancelledError:
            print("\n[用户输入已被取消]")
            return self.SIGNAL_CANCEL  # 如果输入被取消，也视为用户取消任务

        # --- 解析用户输入是普通回复还是指令 ---
        if user_input.lower().strip() == "/cancel":
            print("✅ 已发送 [取消] 信号")
            return self.SIGNAL_CANCEL

        elif user_input.lower().strip() == "/pause":
            print("✅ 已发送 [暂停] 信号")
            return self.SIGNAL_PAUSE

        elif user_input.lower().strip().startswith("/interrupt"):
            parts = user_input.split(" ", 1)
            if len(parts) > 1 and parts[1].strip():
                new_info = parts[1].strip()
                print(f"✅ 已发送 [中断] 信号，附加信息: {new_info}")
                return f"{self.SIGNAL_INTERRUPT_PREFIX} {new_info}"
            else:
                print(
                    "⚠️ [中断] 指令格式错误，需要附加信息。本次输入将作为普通文本处理。"
                )
                return user_input  # 格式错误，则当作普通输入

        else:
            # 如果不是任何指令，则视为普通的用户回复
            return user_input

    def build_user_proxy_assistant(self) -> UserProxyAgent:
        """
        构建并返回一个配置好自定义输入逻辑的 autogen.UserProxyAgent 实例。

        Returns:
            UserProxyAgent: 配置完毕的用户代理智能体。
        """
        user_proxy_agent = UserProxyAgent(
            name=self._name,
            description=self._description,
            # 关键：将我们的自定义异步函数作为输入函数
            input_func=self._custom_input_logic,
        )
        return user_proxy_agent
