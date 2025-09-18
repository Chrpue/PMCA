from enum import StrEnum
from autogen_agentchat.messages import BaseChatMessage
from pydantic import Field


class PMCARoutingMessages(StrEnum):
    TASK_TERMINATE = "[TASK_TERMINATE]"
    TASK_SUCCESS = "[TASK_SUCCESS]"  # 明确表示任务成功完成
    TASK_FAILURE = "[TASK_FAILURE]"

    # --- 用户主动介入信号 ---
    SIGNAL_CANCEL = "[USER_CANCEL]"
    SIGNAL_PAUSE = "[USER_PAUSE]"
    SIGNAL_INTERRUPT_PREFIX = "[USER_INTERRUPT]"

    # --- RoundRobin 团队执行结果 ---
    ROUNDROBIN_SUCCESS = "[ROUNDROBIN_SUCCESS]"
    ROUNDROBIN_FAILURE = "[ROUNDROBIN_FAILURE]"

    # --- 用户被动介入信息 ---
    TEAM_NEED_USER = "[NEED_USER_INTERRUPT]"

    # --- Swarm 团队执行结果 ---
    SWARM_SUCCESS = "[SWARM_SUCCESS]"
    SWARM_FAILURE = "[SWARM_FAILURE]"

    @classmethod
    def user_termination(cls):
        return [item for item in cls if item.name.startswith("SIGNAL_")]

    @classmethod
    def task_termination(cls):
        return [item for item in cls if item.name.startswith("TASK_")]

    @classmethod
    def swarm_termination(cls):
        return [item for item in cls if item.name.startswith("SWARM_")]

    @classmethod
    def roundrobin_termination(cls):
        return [item for item in cls if item.name.startswith("ROUNDROBIN_")]

    @classmethod
    def selector_group_termination(cls):
        return [item for item in cls if item.name.startswith("TASK_")]


class PMCANeedUserInput(BaseChatMessage):
    reason: str = Field(..., description="说明需要用户介入的原因.")
    content: str = "需要用户帮助."
