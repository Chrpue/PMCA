from typing import List, Dict, Any
from autogen_agentchat.base import ChatAgent
from autogen_agentchat.teams import Swarm
from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination

from base.runtime.system_workbench import PMCATaskContext
from core.team.common import PMCARoutingMessages


class PMCASwarmFactory:
    """
    一个通用的工厂，用于根据给定的成员列表，动态创建无中心化的Swarm团队。
    """

    def __init__(self, ctx: PMCATaskContext):
        self._ctx = ctx
        self._termination = self._init_termination()

    def _init_termination(self):
        """
        设置团队的终止条件
        """
        need_user_termination = TextMentionTermination(
            PMCARoutingMessages.TEAM_NEED_USER.value
        )

        task_execute_termination = TextMentionTermination(
            PMCARoutingMessages.SWARM_SUCCESS
        ) | TextMentionTermination(PMCARoutingMessages.SWARM_FAILURE)

        return need_user_termination | task_execute_termination

    def create_swarm(
        self,
        team_name: str,
        participant_names: List[str],
        initial_speaker_name: str,
        max_turns: int = 50,
    ) -> Swarm:
        """
        根据给定的配置，构建一个 Swarm 实例。

        Args:
            team_name (str): 要创建的 Swarm 团队的名称。
            participant_names (List[str]): 参与此 Swarm 的所有智能体的名称列表。
            initial_speaker_name (str): 接收初始任务并开启协作的第一个发言者。
            max_turns (int): Swarm 的最大对话轮次。

        Returns:
            Swarm: 配置完成的 Swarm 实例。
        """
        if initial_speaker_name not in participant_names:
            raise ValueError(
                f"初始发言人 '{initial_speaker_name}' 必须是参与者的一员。"
            )

        # 1. 动态创建所有参与者的实例，并为他们注入 handoffs
        participants: List[ChatAgent] = []
        for name in participant_names:
            # Handoffs 列表是除了自己之外的所有其他成员
            dynamic_handoffs = [
                p_name for p_name in participant_names if p_name != name
            ]

            assistant = self._ctx.assistant_factory.create_assistant(
                name, dynamic_handoffs=dynamic_handoffs
            )
            participants.append(assistant)

        initial_speaker_instance = next(
            p for p in participants if p.name == initial_speaker_name
        )
        participants.remove(initial_speaker_instance)
        participants.insert(0, initial_speaker_instance)

        swarm_team = Swarm(
            name=team_name,
            participants=participants,
            termination_condition=self._termination,
        )

        return swarm_team
