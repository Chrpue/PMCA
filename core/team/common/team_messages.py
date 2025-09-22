from enum import StrEnum
from autogen_agentchat.messages import BaseChatMessage
from pydantic import Field


class PMCARoutingMessages(StrEnum):
    TASK_TERMINATE = "[TASK_TERMINATE]"
    TASK_SUCCESS = "[TASK_SUCCESS]"  # 明确表示任务成功完成
    TASK_FAILURE = "[TASK_FAILURE]"

    # --- 分诊环节信号 ---
    TRIAGE_SUCCESS = "[TRIAGE_SUCCESS]"
    TRIAGE_FAILURE = "[TRIAGE_FAILURE]"

    # --- 用户主动介入信号 ---
    SIGNAL_CANCEL = "[USER_CANCEL]"
    SIGNAL_PAUSE = "[USER_PAUSE]"
    SIGNAL_INTERRUPT_PREFIX = "[USER_INTERRUPT]"

    # --- 复杂任务 团队执行结果 ---
    COMPLEX_EXECUTOR_SUCCESS = "[COMPLEX_EXECUTOR_SUCCESS]"
    COMPLEX_EXECUTOR_FAILURE = "[COMPLEX_EXECUTOR_FAILURE]"

    # --- 简单任务 团队执行结果 ---
    SIMPLE_EXECUTOR_SUCCESS = "[SIMPLE_EXECUTOR_SUCCESS]"
    SIMPLE_EXECUTOR_FAILURE = "[SIMPLE_EXECUTOR_FAILURE]"

    # --- Swarm 团队执行结果 ---
    SWARM_SUCCESS = "[SWARM_SUCCESS]"
    SWARM_FAILURE = "[SWARM_FAILURE]"

    @classmethod
    def user_termination(cls):
        return [item for item in cls if item.name.startswith("SIGNAL_")]

    @classmethod
    def triage_termination(cls):
        return [item for item in cls if item.name.startswith("TRIAGE_")]

    @classmethod
    def task_termination(cls):
        return [item for item in cls if item.name.startswith("TASK_")]

    @classmethod
    def swarm_termination(cls):
        return [item for item in cls if item.name.startswith("SWARM_")]

    @classmethod
    def complex_executor_termination(cls):
        return [item for item in cls if item.name.startswith("COMPLEX_EXECUTOR_")]
