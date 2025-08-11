import os
from typing import Annotated, Literal
from pydantic import BaseModel, Field
from enum import Enum

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.ui import Console


class TeamComponent(str, Enum):
    MAGENTIC_ONE = "Magentic-One"
    SWARM = "Swarm"
    ROUND_ROBIN = "RoundRobin"
    GRAPH_FLOW = "GraphFlow"


class DesicionResponse(BaseModel):
    team: Literal["RoundRobin", "MagenticOne", "Swarm", "GraphFlow"] = Field(
        description="选择最合适的团队组件"
    )
    score: float = Field(description="置信度")
    reason: str = Field(description="做出这样决定的原因(最多输出70字)")


class PMCATaskPreprocessing:
    """Processing Team Decision"""

    @staticmethod
    async def run(
        task: str, decision_agent: AssistantAgent, decision_critic_agent: AssistantAgent
    ):
        # set structured output
        # decision_agent._output_content_type = DesicionResponse
        team = RoundRobinGroupChat(
            [decision_agent, decision_critic_agent],
            TextMentionTermination("APPROVE") | MaxMessageTermination(max_messages=4),
        )

        await Console(team.run_stream(task=task))
