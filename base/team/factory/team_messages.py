from enum import StrEnum
from autogen_agentchat.messages import BaseChatMessage
from pydantic import Field


class TeamFeedBack(StrEnum):
    FINISHED = "[TEAM EXECUTION FINISHED]"
    RESUME = "[TEAM RESUME]"
    NEEDUSER = "[NEED USER INPUT]"
    TEAMDECISIONCOMPLETE = "[TEAM DECISION COMPLETE]"
    AGENTSDECISIONCOMPLETE = "[AGENTS DECISION COMPLETE]"
    TEAMDECISIONREVISE = "[TEAM DECISION REVISE]"
    AGENTSDECISIONREVISE = "[AGENTS DECISION REVISE]"
    OVERALLDECISIONCOMPLETE = "[OVERALL DECISION COMPLETE]"
    QUIT = "QUIT"
    GRAPHFINISHED = "[GRAPH FINISHED]"


class PMCANeedUserInput(BaseChatMessage):
    reason: str = Field(..., description="说明需要用户介入的原因.")
    content: str = "需要用户帮助."
