from enum import StrEnum
from autogen_agentchat.messages import BaseChatMessage
from pydantic import Field


class PMCARoutingMessages(StrEnum):
    TASK_TERMINATE = "[TASK_TERMINATE]"

    # --- 用户主动介入信号 ---
    SIGNAL_CANCEL = "[USER_CANCEL]"
    SIGNAL_PAUSE = "[USER_PAUSE]"
    SIGNAL_INTERRUPT_PREFIX = "[USER_INTERRUPT]"

    # --- 用户被动介入信息 ---
    TEAM_NEED_USER = "[NEED_USER_INTERRUPT]"

    # --- Swarm 团队执行结果 ---
    SWARM_SUCCESS = "[SWARM_SUCCESS]"
    SWARM_FAILURE = "[SWARM_FAILURE]"


class PMCANeedUserInput(BaseChatMessage):
    reason: str = Field(..., description="说明需要用户介入的原因.")
    content: str = "需要用户帮助."
