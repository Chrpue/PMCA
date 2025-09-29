from typing import Union
from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.ollama import OllamaChatCompletionClient
from autogen_ext.models.openai import OpenAIChatCompletionClient


class PMCACodeGenerator:
    def __init__(
        self,
        model_client: Union[OpenAIChatCompletionClient, OllamaChatCompletionClient],
    ) -> None:
        self._model_client = model_client
        self.system_message = """你是一个强大的 AI 助手，使用你的编码和语言能力来解决任务，你只关注生成高质量的代码来完成工作而无需亲自执行.
生成 Python 代码(放在 python 代码块中)或 Shell 脚本(放在 sh 代码块中).
你在执行任务时的逻辑:
如果需要，分步骤解决问题。如果没有提供计划，先解释你的计划。清晰地标注哪个步骤使用代码，哪个步骤使用语言说明.
使用代码时，必须在代码块中指明脚本类型。用户只能执行你提供的代码，不能对其进行修改。因此，不要建议需要用户改动的未完成代码.
不要在一次回复中包含多个代码块。不要要求用户复制粘贴结果，而应在代码中使用 print 函数来输出结果。检查用户执行后的结果。如果结果显示有错误，修复错误并重新输出完整代码，而非补丁式修改。如果无法修复错误或代码执行成功后仍未解决问题，则分析原因、检验假设、收集更多信息并尝试其他方法。
当你找到答案时，请仔细验证，并在回复中提供可验证的证据（如果可能）
"""

        self._agent = None

    def _create(self) -> AssistantAgent:
        return AssistantAgent(
            name="PMCACodeGenerator",
            description="代码生成器，具备出色的语言能力、Python 编程技能和 Linux 命令行操作能力",
            model_client=self._model_client,
            system_message=self.system_message,
            tools=[],
        )

    @property
    def agent(self):
        """The agent property."""
        return self._create()

    @agent.setter
    def agent(self, value):
        self._agent = value
