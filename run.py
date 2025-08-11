import asyncio

from autogen_agentchat.conditions import TextMentionTermination
from autogen_agentchat.teams import RoundRobinGroupChat
from dotenv import load_dotenv
from autogen_core import SingleThreadedAgentRuntime
from autogen_core import AgentId, MessageContext, RoutedAgent, message_handler
from autogen_agentchat.ui import Console
from typing import Annotated, Literal
from pydantic import BaseModel, Field
from client.llm_client import LLMClient
from assistants.task_preprocessing import PMCATaskPreprocessing
from base.agents.factory import PMCAAgentFactory
from base.memory import PMCADecisionMemory, PMCADecisionCriticMemory

load_dotenv()

model_client = LLMClient.get_llm_client("qwen", "base")


pmca_decision_memory = PMCADecisionMemory()
pmca_decision_critic_memory = PMCADecisionCriticMemory()

pmca_agents_factory = PMCAAgentFactory(model_client=model_client)


class DesicionResponse(BaseModel):
    team: Literal["RoundRobin", "MagenticOne", "Swarm", "GraphFlow"] = Field(
        description="选择最合适的团队组件"
    )
    score: float = Field(description="置信度")
    reason: str = Field(description="做出这样决定的原因(最多输出70字)")


pmca_team_decision_agent = pmca_agents_factory.create_agent(
    "PMCATeamDecision",
    memory=[pmca_decision_memory],
    output_content_type=DesicionResponse,
)


pmca_team_decision_critic_agent = pmca_agents_factory.create_agent(
    "PMCATeamDecisionCritic", memory=[pmca_decision_critic_memory]
)


async def main(task):
    return await PMCATaskPreprocessing.run(
        task, pmca_team_decision_agent, pmca_team_decision_critic_agent
    )


if __name__ == "__main__":
    task = "查询昨天的报警信息"
    asyncio.run(main(task))
