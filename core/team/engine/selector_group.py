from typing import List, Sequence, Tuple, cast
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.base import ChatAgent, Team
from autogen_agentchat.messages import BaseAgentEvent, BaseChatMessage
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
        self._participants, self._participant_descriptions = (
            self._build_participants_and_descriptions()
        )

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

    def _build_participants_and_descriptions(
        self,
    ) -> Tuple[List[ChatAgent | Team], str]:
        """
        动态构建所有参与者，并生成一份能力清单字符串，用于注入到Orchestrator的提示词中。
        """

        participants: List[ChatAgent | Team] = []
        descriptions_list: List[str] = []

        # 1. 动态发现并创建所有领域专家团队（占位符）
        all_registered_metas = (
            self._ctx.assistant_factory.get_all_registered_assistants()
        )
        for name, meta in all_registered_metas.items():
            # 约定：凡是定义了 domains 的，都是可供 Orchestrator 调度的独立执行单元
            if meta.domains and name != PMCACoreAssistants.ORCHESTRATOR.value:
                # 未来这里可以根据 meta 的类型来决定是创建 AssistantAgent 还是一个完整的 Team 对象
                expert_team_placeholder = self._ctx.assistant_factory.create_assistant(
                    name
                )
                participants.append(expert_team_placeholder)
                descriptions_list.append(
                    f"- {expert_team_placeholder.name}: {meta.duty}"
                )  # 使用 duty 作为更详细的职能描述

        # 2. 创建并添加核心智能体
        user_proxy = self._build_user_proxy()
        participants.append(user_proxy)
        descriptions_list.append(
            f"- {user_proxy.name}: 负责处理所有需要人类介入的场景，包括回答问题和发送控制指令。"
        )

        # 3. 为 Orchestrator 准备动态提示词
        #    首先获取能力清单，注意要把Orchestrator自己排除在外
        available_executors_str = "\n".join(descriptions_list)

        #    然后获取Orchestrator的元数据和原始提示词模板
        orchestrator_meta = all_registered_metas[PMCACoreAssistants.ORCHESTRATOR.value]
        final_system_message = orchestrator_meta.system_message.format(
            available_executors=available_executors_str
        )

        #    【核心修正】在创建 Orchestrator 时，将格式化好的 system_message 作为覆盖参数传入
        orchestrator = self._ctx.assistant_factory.create_assistant(
            biz_type=PMCACoreAssistants.ORCHESTRATOR.value,
            system_message=final_system_message,  # 覆盖默认的系统提示词
        )
        participants.insert(0, orchestrator)  # 将Orchestrator放在列表首位

        # 准备完整的角色描述，这次包含Orchestrator自己，用于 selector_prompt
        full_descriptions_str = (
            f"- {orchestrator.name}: {orchestrator.description}\n"
            + available_executors_str
        )

        logger.info(
            f"动态发现的SelectorGroup参与者名单: {[p.name for p in participants]}"
        )
        logger.info(
            f"动态生成并注入到Orchestrator的能力清单:\n{available_executors_str}"
        )

        return participants, full_descriptions_str

    def _probe_selector_function(
        self,
        participants: List[ChatAgent | Team],
        messages: Sequence[BaseAgentEvent | BaseChatMessage],
    ) -> str | None:
        """
        一个用于调试的探针，它不进行任何选择，
        只是打印出最近的对话历史和角色列表，然后返回 None，让 LLM 继续进行选择。

        Args:
            participants: 当前群聊的参与者列表。
            messages: 对话历史消息列表。
        """
        print("\n" + "=" * 50)
        print("🕵️  [Selector Probe] 探针已触发 🕵️")

        # 打印 {roles} 的内容
        print("\n--- [Roles Content] ---")
        roles_text = ""
        for agent in participants:
            roles_text += f"{agent.name}: {agent.description}\n"
        print(roles_text)

        # 打印 {history} 的内容
        print("\n--- [History Content] ---")
        history_text = ""
        for msg in messages:
            # BaseChatMessage 有一个 to_text() 方法，可以方便地获取其文本内容
            if isinstance(msg, BaseChatMessage):
                history_text += f"{msg.source}: {msg.content}\n\n"  # type: ignore
        print(history_text)

        print("=" * 50 + "\n")

        return None

    def build(self) -> SelectorGroupChat:
        return SelectorGroupChat(
            self._participants,
            model_client=self._ctx.llm_factory.client(),
            termination_condition=self._termination,
            selector_prompt=SELECTOR_PROMPT,
            # selector_func=lambda messages: self._probe_selector_function(
            #     self._participants, messages
            # ),
            allow_repeated_speaker=True,
        )
