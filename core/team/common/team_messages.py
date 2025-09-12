from enum import StrEnum
from autogen_agentchat.messages import BaseChatMessage
from pydantic import Field


class PMCARoutingMessages(StrEnum):
    TASK_TERMINATE = "[TASK TERMINATE]"
    SIGNAL_CANCEL = "[USER_CANCEL]"
    SIGNAL_PAUSE = "[USER_PAUSE]"
    SIGNAL_INTERRUPT_PREFIX = "[USER_INTERRUPT]"


class PMCANeedUserInput(BaseChatMessage):
    reason: str = Field(..., description="说明需要用户介入的原因.")
    content: str = "需要用户帮助."
