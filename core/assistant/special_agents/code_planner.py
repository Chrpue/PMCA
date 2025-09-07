from typing import Union
from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.ollama import OllamaChatCompletionClient
from autogen_ext.models.openai import OpenAIChatCompletionClient


class PMCACodeExecPlanner:
    def __init__(
        self,
        model_client: Union[OpenAIChatCompletionClient, OllamaChatCompletionClient],
    ) -> None:
        self._model_client = model_client
        self.system_message = """
你是一个任务规划者智能体，负责接收用户任务，并协调代码生成与执行过程，监督任务的整体进展。你的职责包括：

1. 分析用户提供的任务，明确其目标和要求。
2. 指导代码生成助手根据任务需求生成代码。
3. 指导执行助手执行生成的代码，并收集执行结果。
4. 根据执行结果评估任务是否完成，判断成功或失败。
5. 任务完成后使用 'CODE_EXEC_SUCCESS' 表示任务执行成功，或 'CODE_EXEC_FAILURE' 表示任务执行失败.

请注意：
- 在任务进行过程中，不要提前输出总结性回复或上述关键词，直到任务确实完成。
- 在整个过程中，保持对任务状态的监督，确保各个步骤按预期进行。
- 任务结束后务必加上'CODE_EXEC_SUCCESS' 或 'CODE_EXEC_FAILURE'关键字.
"""

        self._agent = None

    def _create(self) -> AssistantAgent:
        return AssistantAgent(
            name="PMCACodeExecPlanner",
            description="对代码生成与执行进行任务派分和结果总结的助手",
            model_client=self._model_client,
            system_message=self.system_message,
        )

    @property
    def agent(self):
        """The agent property."""
        return self._create()

    @agent.setter
    def agent(self, value):
        self._agent = value
