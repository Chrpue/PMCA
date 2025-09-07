from typing import Union, List
from autogen_agentchat.agents import AssistantAgent, CodeExecutorAgent
from autogen_agentchat.base import ChatAgent, TerminationCondition
from autogen_agentchat.teams import MagenticOneGroupChat, RoundRobinGroupChat
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_ext.models.ollama import OllamaChatCompletionClient
from autogen_agentchat.conditions import (
    TextMentionTermination,
    MaxMessageTermination,
    StopMessageTermination,
    TextMessageTermination,
)

from core.agents.factory import PMCAAgentFactory, PMCASpecialAgents
from core.agents import PMCACoder, PMCAExecutor
from core.team.strategy import PMCATeam
from client.llm_client import LLMClient


class PMCARoundRobin(PMCATeam):
    """Custom roundrobin"""

    def __init__(
        self,
        origin_task: str,
        model_client: Union[OpenAIChatCompletionClient, OllamaChatCompletionClient],
    ):
        super().__init__(origin_task, model_client)

    def termination(self) -> TerminationCondition:
        """设置群组的终止条件"""
        return (
            TextMentionTermination("TERMINATE")
            | MaxMessageTermination(max_messages=80)
            | TextMentionTermination("APPROVE", sources="PMCAUser")
        )

    def create(self, factory: PMCAAgentFactory, participants: List[str]):
        """构建RoundRobin群组"""

        participants_list: List[ChatAgent] = []

        for partner in participants:
            if partner not in PMCASpecialAgents:
                participants_list.append(factory.create_agent(partner))

            elif partner == "PMCACoder":
                participants_list.append(factory.create_agent(partner))
                computer_terminal = PMCAExecutor().agent
                self._executor = PMCAExecutor().executor
                participants_list.append(computer_terminal)

                self._use_docker = True

        return RoundRobinGroupChat(
            participants_list,
            termination_condition=self._termination,
        )
