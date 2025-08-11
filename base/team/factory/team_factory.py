import asyncio
from abc import ABCMeta, abstractmethod
from typing import Literal, TypeVar, Union, Optional, List
from autogen_agentchat.ui import Console
from autogen_agentchat.teams import (
    SelectorGroupChat,
    MagenticOneGroupChat,
    Swarm,
    RoundRobinGroupChat,
    GraphFlow,
)
from autogen_core import CancellationToken
from autogen_agentchat.base import TerminationCondition
from autogen_agentchat.conditions import ExternalTermination
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_ext.models.ollama import OllamaChatCompletionClient
from autogen_ext.code_executors.docker import DockerCommandLineCodeExecutor

from base.agents.factory import PMCAAgentFactory


TeamComponentType = Union[
    SelectorGroupChat,
    MagenticOneGroupChat,
    Swarm,
    RoundRobinGroupChat,
    GraphFlow,
]


class PMCATeam(metaclass=ABCMeta):
    def __init__(
        self,
        factory: PMCAAgentFactory,
        model_client: Union[OpenAIChatCompletionClient, OllamaChatCompletionClient],
    ):
        self._factory = factory
        self._cancellation_token = CancellationToken()
        self._external_termination = ExternalTermination()
        self._termination = self.termination() | self._external_termination
        self._model_client: Union[
            OpenAIChatCompletionClient, OllamaChatCompletionClient
        ] = model_client

        self._use_docker = False
        self._executor: Optional[DockerCommandLineCodeExecutor] = None

    @abstractmethod
    def create(self, participants: List[str] = []) -> TeamComponentType:
        """初始化群组"""
        pass

    @abstractmethod
    def termination(self) -> TerminationCondition:
        """设置群组的终止条件"""
        pass

    @property
    def executor(self):
        """The executor property."""
        return self._executor

    @property
    def use_docker(self):
        """The use_docker property."""
        return self._use_docker

    @use_docker.setter
    def use_docker(self, use_docker_):
        self._use_docker = use_docker_

    @property
    def cancellation_token(self):
        """The cancellation_token property."""
        return self._cancellation_token

    @cancellation_token.setter
    def cancellation_token(self, cancellation_token_):
        """The cancellation_token property."""
        self._cancellation_token = cancellation_token_

    @cancellation_token.setter
    def cancellation_token(self, value):
        self._cancellation_token = value

    async def stop(self):
        """暂停任务"""
        self._external_termination.set()

    async def cancel(self):
        """取消任务"""
        self._cancellation_token.cancel()

    async def reset(self):
        """重置群组"""
        await self._team.reset()

    async def console(self, task, team):
        if self._executor:
            await self._executor.start()
        await Console(
            team.run_stream(task=task, cancellation_token=self._cancellation_token)
        )

        if self._executor:
            await self._executor.stop()
