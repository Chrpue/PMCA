from typing import AsyncGenerator, Literal
from loguru import logger

from autogen_agentchat.base import Response, TaskResult
from autogen_agentchat.messages import BaseAgentEvent, BaseChatMessage, TextMessage
from autogen_agentchat.ui import Console
from .team_factory import PMCATeam, TeamComponentType
from .team_messages import PMCANeedUserInput, TeamFeedBack


class PMCATeamExecutor:
    """Team Component Execute Processing"""

    def __init__(self, participants, team_factory: PMCATeam) -> None:
        self._team_factory = team_factory
        self._participants = participants
        self._team_component: TeamComponentType = self._team_factory.create(
            self._participants
        )

    # mode: Literal["console", "stream"] = "console"
    async def process(self, task):
        if "PMCACodeGenExec" in self._participants:
            self._team_factory.use_docker = True

        use_docker = self._team_factory.use_docker
        executor = self._team_factory.executor

        if use_docker:
            await executor.start()
        try:
            async for ev in self._team_component.run_stream(
                task=task,
                cancellation_token=self._team_factory.cancellation_token,
            ):
                # 如果团队请求用户输入，则转发该请求消息后中断执行
                if isinstance(ev, BaseChatMessage) and TeamFeedBack.NEEDUSER in ev.content:
                    yield ev  # 将原始请求消息交由 TeamBootstrapProxy 处理暂停逻辑
                    break
                # 如果团队任务完成，停止迭代（不在此生成 FINISHED，由上层处理）
                if isinstance(ev, TaskResult):
                    break
                # 其他一般消息，直接向上层产出
                yield ev
        finally:
            if use_docker:
                await executor.stop()

    @property
    def team_component(self):
        """The team_component property."""
        return self._team_component

    @team_component.setter
    def team_component(self, value):
        self._team_component = value
