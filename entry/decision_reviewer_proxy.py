from loguru import logger
from typing import Sequence, AsyncGenerator
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.base import Response
from autogen_core import CancellationToken
from autogen_agentchat.messages import BaseAgentEvent, BaseChatMessage

from base.agents.special_agents import PMCADecision


class DecisionReviewerProxy(AssistantAgent):
    """Wraps the original decision_reviewer to dump JSON plan to Workbench."""

    def __init__(self, wrapped: AssistantAgent, cfg, llm_cfg):
        super().__init__(
            name=wrapped.name,
            description=wrapped.description,
            system_message=wrapped.getattr(wrapped, "system_message", None)  # type: ignore
            or getattr(wrapped, "config", {}).system_message  # type: ignore
            if hasattr(wrapped, "config")
            else None,
            model_client=llm_cfg.model_client,
        )
        self._wrapped = wrapped
        self._workbench = cfg.app_workbench
        self._cfg = cfg
        self._llm_cfg = llm_cfg

    @property
    def produced_message_types(self) -> Sequence[type[BaseChatMessage]]:
        return self._wrapped.produced_message_types

    async def on_messages_stream(
        self,
        messages: Sequence[BaseChatMessage],
        cancellation_token: CancellationToken,
    ) -> AsyncGenerator[BaseAgentEvent | BaseChatMessage | Response, None]:
        last_resp: Response | None = None
        async for ev in self._wrapped.on_messages_stream(messages, cancellation_token):
            if isinstance(ev, Response):
                last_resp = ev
            yield ev

        if last_resp is None:
            return

        try:
            if not self._llm_cfg.llm_support_structured:
                decision_response_plan = PMCADecision.deepseek_decision_response(
                    last_resp.chat_message.content  # type: ignore
                )
            else:
                decision_response_plan = last_resp.chat_message.content  # type: ignore
            await self._workbench.set_item("entry_decision", decision_response_plan)
        except Exception as e:
            logger.error(f"无法将抉择结果保存至workbench…… {e}")
