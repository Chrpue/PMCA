from typing import List

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.base import Response
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.messages import BaseChatMessage, TextMessage
from autogen_agentchat.conditions import MaxMessageTermination

from base.runtime import PMCATaskContext
from core.team.common import PMCATriageResult

# 导入模型信息以检查结构化输出支持
from core.client.model_info import supports_structured_output
from core.client.llm_factory import ProviderType


class TriageProxyAgent(AssistantAgent):
    """
    分诊团队的代理节点。
    它在 GraphFlow 中代表整个分诊流程，内部封装了一个 RoundRobinGroupChat。
    """

    def __init__(self, ctx: PMCATaskContext, **kwargs):
        super().__init__(**kwargs)
        self._ctx = ctx

    async def on_messages(self, messages: List[BaseChatMessage]) -> Response:
        """
        当 GraphFlow 激活此节点时，此方法被调用。
        """
        factory = self._ctx.assistant_factory

        # 1. 动态构建分诊团队 (RoundRobinGroupChat)
        user_proxy = factory.create_assistant("PMCAUserProxy")

        all_metas = factory.get_all_registered_assistants()
        available_executors = {
            name: meta.duty for name, meta in all_metas.items() if meta.domains
        }
        available_executors_str = "\n".join(
            [f"- {name}: {duty}" for name, duty in available_executors.items()]
        )

        provider_str = self._ctx.task_env.DEFAULT_PROVIDER
        model_str = self._ctx.task_env.DEFAULT_MODEL
        supports_structured = supports_structured_output(
            ProviderType(provider_str), model_str
        )

        creation_kwargs = {}
        if supports_structured:
            from base.prompts.task_parser import STRUCTURED_OUTPUT_SYSTEM_MESSAGE

            prompt_template = STRUCTURED_OUTPUT_SYSTEM_MESSAGE
            creation_kwargs["output_content_type"] = PMCATriageResult
        else:
            from base.prompts.task_parser import JSON_BASED_SYSTEM_MESSAGE

            prompt_template = JSON_BASED_SYSTEM_MESSAGE

        parser_prompt = prompt_template.format(
            available_executors=available_executors_str,
            mission=messages[-1].content,  # 使用 GraphFlow 传递过来的最新任务
        )
        task_parser = factory.create_assistant(
            biz_type="PMCATaskParser", system_message=parser_prompt, **creation_kwargs
        )

        triage_team = RoundRobinGroupChat(
            participants=[user_proxy, task_parser],
            termination_condition=MaxMessageTermination(
                max_messages=self._ctx.task_env.TRIAGE_MAX_TURNS
            ),
        )

        # 2. 运行分诊团队
        result = await triage_team.run(task=messages[-1])

        # 3. 提取 TriageResult 并将其作为自己的发言返回给 GraphFlow
        final_triage_result = None
        for msg in reversed(result.messages):
            if msg.source == "PMCATaskParser":
                content = msg.content
                if isinstance(content, PMCATriageResult):
                    final_triage_result = content
                    break

        if not final_triage_result:
            final_triage_result = PMCATriageResult(
                task_type="complex_task",
                comment="分诊失败，默认进入复杂模式。",
                required_executors=None,
            )

        # 将 TriageResult 包装在 TextMessage 中，这样 GraphFlow 的条件函数才能处理
        return Response(
            chat_message=TextMessage(
                source=self.name, content=final_triage_result.model_dump_json()
            )
        )
