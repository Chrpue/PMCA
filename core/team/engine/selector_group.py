from loguru import logger
from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
from autogen_agentchat.teams import SelectorGroupChat

from base.runtime import PMCATaskContext
from core.team.core_assistants import PMCACoreAssistants

from core.team.common import PMCARoutingMessages
from core.team.core_assistants import PMCAUserProxy

from base.prompts import SELECTOR_PROMPT


class PMCASelectorGroup:
    def __init__(self, ctx: PMCATaskContext) -> None:
        self._ctx = ctx
        self._termination = self._termination_condition()

    def _termination_condition(self):
        """
        定义顶层团队的终止条件。
        - 达到最大轮次。
        - Planner 发出任务完成信号。
        - UserProxy 发出取消或暂停信号。
        """
        max_messages_termination = MaxMessageTermination(
            self._ctx.task_env.SELECTOR_GROUP_MAX_TURNS
        )

        # 监听来自 Planner 的完成信号
        text_mention_termination = TextMentionTermination(
            PMCARoutingMessages.TASK_TERMINATE.value,
            PMCACoreAssistants.ORCHESTRATOR,
        )

        # 监听来自 UserProxy 的信号
        user_mention_termination = TextMentionTermination(
            PMCARoutingMessages.SIGNAL_CANCEL.value, PMCACoreAssistants.USER_PROXY
        )

        return (
            text_mention_termination
            | user_mention_termination
            | max_messages_termination
        )

    def _build_orchestrator(self):
        try:
            orchestrator = self._ctx.assistant_factory.create_assistant(
                biz_type=PMCACoreAssistants.ORCHESTRATOR.value
            )
        except Exception as e:
            logger.error(f"创建 {PMCACoreAssistants.ORCHESTRATOR} 失败: {e}")
            raise
        return orchestrator

    def _build_user_proxy(self):
        user_proxy = PMCAUserProxy().build_user_proxy_assistant()
        return user_proxy

    # def _build_swarm_teams(self):

    def build(self) -> SelectorGroupChat:
        orchestrator = self._build_orchestrator()
        user_proxy = self._build_user_proxy()

        participants = [orchestrator, user_proxy]

        return SelectorGroupChat(
            participants,
            model_client=self._ctx.llm_factory.client(),
            termination_condition=self._termination,
            selector_prompt=SELECTOR_PROMPT,
            allow_repeated_speaker=True,
        )
