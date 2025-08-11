import asyncio
from typing import List, Union, Optional

from autogen_agentchat.base import ChatAgent, TerminationCondition
from autogen_core import AgentRuntime

from autogen_agentchat.teams import MagenticOneGroupChat
from autogen_agentchat.ui import Console
from autogen_ext.agents.web_surfer import MultimodalWebSurfer
from autogen_ext.models.ollama import OllamaChatCompletionClient
from autogen_ext.models.openai import OpenAIChatCompletionClient
# from autogen_ext.agents.file_surfer import FileSurfer
# from autogen_ext.agents.magentic_one import MagenticOneCoderAgent
# from autogen_agentchat.agents import CodeExecutorAgent
# from autogen_ext.code_executors.local import LocalCommandLineCodeExecutor

from client.llm_client import LLMClient


class M1Team:
    def __init__(
        self,
        participants: List[ChatAgent],
        model_client: Union[OpenAIChatCompletionClient, OllamaChatCompletionClient],
        termination_condition: Optional[TerminationCondition],
        max_turns: Optional[int] = 20,
        runtime: Optional[AgentRuntime] = None,
        max_stalls: int = 3,
    ):
        self._participants = participants
        self._model_client = model_client
        self._termination_condition = termination_condition
        self._max_turns = max_turns
        self._runtime = runtime
        self._max_stalls = max_stalls

    def obtain(self):
        return MagenticOneGroupChat(
            self._participants,
            self._model_client,
            termination_condition=self._termination_condition,
            max_turns=self._max_turns,
            runtime=self._runtime,
            max_stalls=self._max_stalls,
        )
