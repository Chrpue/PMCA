import asyncio

from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
from autogen_agentchat.teams import RoundRobinGroupChat
from dotenv import load_dotenv
from autogen_core import SingleThreadedAgentRuntime
from autogen_core import AgentId, MessageContext, RoutedAgent, message_handler
from autogen_agentchat.ui import Console
from typing import Annotated, Literal
from pydantic import BaseModel, Field
from client.llm_client import LLMClient
from assistants.task_preprocessing import PMCATaskPreprocessing
from base.agents.abstract import PMCAAgentFactory
from base.memory import PMCADecisionMemory, PMCADecisionCriticMemory

load_dotenv()

model_client = LLMClient.get_llm_client("qwen", "base")


pmca_agents_factory = PMCAAgentFactory(model_client=model_client)


pmca_planner_agent = pmca_agents_factory.create_agent("PMCAPlanner")


pmca_inspector_agent = pmca_agents_factory.create_agent("PMCAInspector")

max_msg_termination = MaxMessageTermination(max_messages=20)
text_termination = TextMentionTermination("TERMINATE")
team = RoundRobinGroupChat(
    [pmca_planner_agent, pmca_inspector_agent],
    text_termination | max_msg_termination,
)

if __name__ == "__main__":
    task = "帮我查看目录/data下都有哪些文件"
    # task = "你的工具列表有哪些"
    asyncio.run(Console(team.run_stream(task=task)))
