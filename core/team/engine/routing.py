from loguru import logger
from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
from autogen_agentchat.teams import SelectorGroupChat

from base.runtime import PMCATaskContext
from core.team.core_assistants import PMCACoreAssistants

from core.team.common import PMCARoutingMessages


class PMCARoutingSelector:
    def __init__(self, ctx: PMCATaskContext) -> None:
        self._ctx = ctx
        self._termination = self._termination_condition()

    def _termination_condition(self):
        max_messages_termination = MaxMessageTermination(self._ctx.task_env.SELECTOR_GROUP_MAX_TURNS)
        text_mention_termination = TextMentionTermination(PMCARoutingMessages.TASK_TERMINATE)
        return text_mention_termination | max_messages_termination

    def _build_orchestrator(self):
        try:
            orchestrator = self._ctx.agent_factory.create_agent(biz_type=PMCACoreAssistants.ORCHESTRATOR)
        except Exception as e:
            logger.error(f"创建 {PMCACoreAssistants.ORCHESTRATOR} 失败: {e}")
            raise
        return orchestrator

    def _build_core_participants(self, ctx):



    def _build_selector_group(self):
        model_client = self._ctx.llm_factory.client()
        global_team = SelectorGroupChat(
            [],
            model_client= model_client,
            termination_condition=self._termination,
            selector_prompt=,
            allow_repeated_speaker=True,
        )
