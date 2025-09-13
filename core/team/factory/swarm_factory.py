# core/team/factory/swarm_factory.py (重构)

from typing import List
from autogen_agentchat.teams import Swarm
from autogen_agentchat.conditions import MaxMessageTermination

from base.runtime.system_workbench import PMCATaskContext


class PMCASwarmFactory:
    """
    一个通用的工厂，用于根据给定的成员列表，动态创建无中心化的Swarm团队。
    """

    def __init__(self, ctx: PMCATaskContext):
        self._ctx = ctx

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
        participants = []
        for name in participant_names:
            # Handoffs 列表是除了自己之外的所有其他成员
            dynamic_handoffs = [
                p_name for p_name in participant_names if p_name != name
            ]

            assistant = self._ctx.assistant_factory.create_assistant(
                name, dynamic_handoffs=dynamic_handoffs
            )
            participants.append(assistant)

        # 2. 确保初始发言者在列表的第一位，这是 Swarm 启动的要求
        # 找到初始发言者实例
        initial_speaker_instance = next(
            p for p in participants if p.name == initial_speaker_name
        )
        # 将它移动到列表首位
        participants.remove(initial_speaker_instance)
        participants.insert(0, initial_speaker_instance)

        # 3. 定义终止条件
        termination_condition = MaxMessageTermination(max_messages=max_turns)

        # 4. 实例化并返回 Swarm
        swarm_team = Swarm(
            name=team_name,
            participants=participants,
            termination_condition=termination_condition,
        )

        return swarm_team
