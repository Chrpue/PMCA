from typing import Union
from autogen_agentchat.base import TerminationCondition
from autogen_agentchat.teams import MagenticOneGroupChat
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_ext.models.ollama import OllamaChatCompletionClient
from autogen_agentchat.conditions import (
    TextMentionTermination,
    MaxMessageTermination,
    StopMessageTermination,
    TextMessageTermination,
)

from core.team.factory import PMCATeam
from core.agents import PMCAUser, PMCAFileSurfer


class PMCAM1(PMCATeam):
    """Magentic-One团队组件"""

    def termination(self) -> TerminationCondition:
        """设置群组的终止条件"""
        return (
            TextMentionTermination("TERMINATE")
            | MaxMessageTermination(max_messages=80)
            | TextMentionTermination("APPROVE", sources="PMCAUser")
        )

    def create(self, participants):
        """构建Magentic-One群组"""

        coder = self._factory.create_agent("PMCACoder")
        computer_terminal = PMCAExecutor()
        pmca_executor = computer_terminal.agent
        self._executor = computer_terminal.executor

        pmca_filesurfer = self._factory.create_agent("PMCAFileSurfer")

        return MagenticOneGroupChat(
            [coder, pmca_executor, pmca_filesurfer],
            model_client=self._model_client,
            termination_condition=self._termination,
        )
