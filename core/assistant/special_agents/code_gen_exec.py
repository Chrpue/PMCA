from typing import Union, List, Sequence
from autogen_agentchat.base import TerminatedException, TerminationCondition
from autogen_agentchat.tools import TeamTool
from autogen_core import Component
from autogen_ext.models.ollama import OllamaChatCompletionClient
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_agentchat.messages import (
    BaseAgentEvent,
    BaseChatMessage,
    StopMessage,
    ToolCallExecutionEvent,
)
from autogen_agentchat.teams import RoundRobinGroupChat
from pydantic import BaseModel

from .code_planner import PMCACodeExecPlanner
from .code_executor import PMCACodeExecutor
from .code_generator import PMCACodeGenerator


class CodingTaskTerminationConfig(BaseModel):
    max_rounds: int = 10
    function_name: str = "code_gen_exec_complete"
    keywords: List[str] = ["CODE_EXEC_SUCCESS", "CODE_EXEC_FAILURE"]


class CodingTaskTerminationCondition(
    TerminationCondition, Component[CodingTaskTerminationConfig]
):
    """
    支持序列化的自定义终止条件：
    1. 限制最大消息轮数；
    2. 检测特定工具函数调用完成；
    3. 检测消息中出现特定关键字。
    任意条件满足即触发终止。
    """

    component_config_schema = CodingTaskTerminationConfig
    component_provider_override = (
        "base.agents.special_agents.code_gen_exec.CodingTaskTerminationCondition"
    )

    def __init__(
        self,
        max_rounds: int = 20,
        keywords: List[str] = ["CODE_EXEC_SUCCESS", "CODE_EXEC_FAILURE"],
        function_name: str = "code_gen_exec_complete",
    ) -> None:
        self.max_rounds = max_rounds
        self.keywords = keywords or ["CODE_EXEC_SUCCESS", "CODE_EXEC_FAILURE"]
        self.function_name = function_name
        self._message_count = 0
        self._terminated = False

    async def reset(self):
        """重置状态，支持复用"""
        self._message_count = 0
        self._terminated = False

    @property
    def terminated(self):
        return self._terminated

    async def __call__(
        self, messages: Sequence[BaseAgentEvent | BaseChatMessage]
    ) -> StopMessage | None:
        if self._terminated:
            raise TerminatedException("Termination condition has already been reached")

        for msg in messages:
            # 条件2：工具调用结果事件检测
            if isinstance(msg, ToolCallExecutionEvent):
                func_result = getattr(msg, "payload", None)
                if (
                    func_result
                    and getattr(func_result, "name", "") == self.function_name
                ):
                    self._terminated = True
                    return StopMessage(
                        content=f"Function '{self.function_name}' was executed, triggering termination.",
                        source="CodingTaskTerminationCondition",
                    )
            # 条件3：内容关键词检测
            if hasattr(msg, "content") and isinstance(
                msg.content,  # type: ignore
                str,
            ):  # typing ignore
                for kw in self.keywords:
                    if kw in msg.content:  # type: ignore
                        self._terminated = True
                        return StopMessage(
                            content=f"Keyword '{kw}' found in message, triggering termination.",
                            source="CodingTaskTerminationCondition",
                        )

        self._message_count += len(messages)

        # 条件1：轮次数检测
        if self.max_rounds is not None and self._message_count >= self.max_rounds:
            self._terminated = True
            return StopMessage(
                content=f"Reached max rounds limit: {self.max_rounds}.",
                source="CodingTaskTerminationCondition",
            )

        return None

    # 组件序列化支持方法
    def _to_config(self) -> CodingTaskTerminationConfig:
        return CodingTaskTerminationConfig(
            max_rounds=self.max_rounds,
            function_name=self.function_name,
            keywords=self.keywords,
        )

    @classmethod
    def _from_config(
        cls, config: CodingTaskTerminationConfig
    ) -> "CodingTaskTerminationCondition":
        return cls(
            max_rounds=config.max_rounds,
            function_name=config.function_name,
            keywords=config.keywords,
        )


class PMCACodeGenExecTool:
    def __init__(
        self,
        model_client: Union[OpenAIChatCompletionClient, OllamaChatCompletionClient],
    ) -> None:
        self._model_client = model_client
        self._planner = PMCACodeExecPlanner(self._model_client).agent
        self._generator = PMCACodeGenerator(self._model_client).agent
        pmca_code_executor = PMCACodeExecutor()
        self._executor = pmca_code_executor.agent
        self._docker_exec = pmca_code_executor.executor
        self._team_tool = None
        self._termination_condition = None

    @property
    def team_tool(self):
        """The team_tool property."""
        return self._create_team_tool()

    @property
    def docker_exec(self):
        """The docker_exec property."""
        return self._docker_exec

    def _create_team_tool(self):
        self._termination_condition = CodingTaskTerminationCondition(
            max_rounds=10,
            function_name="code_gen_exec_complete",
            keywords=["CODE_EXEC_SUCCESS", "CODE_EXEC_FAILURE"],
        )

        return TeamTool(
            name="PMCACodeGenExecTool",
            description="一个自动编码与执行代码的多轮任务处理团队",
            team=RoundRobinGroupChat(
                [
                    self._planner,
                    self._generator,
                    self._executor,
                ],
                termination_condition=self._termination_condition,
                max_turns=10,
            ),
        )
