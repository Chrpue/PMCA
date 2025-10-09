from typing import List
from loguru import logger
from autogen_agentchat.base import ChatAgent, Team
from autogen_agentchat.teams import Swarm
from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
from base.runtime.task_context import PMCATaskContext
from core.team.common.team_messages import PMCARoutingMessages
from core.team.factory import PMCATeamFactory
from core.team.engine.termination import PMCASwarmTermination


class PMCASwarm(PMCATeamFactory):
    def __init__(
        self,
        ctx: PMCATaskContext,
        name: str,
        description: str,
        use_user: bool = False,
    ) -> None:
        super().__init__(ctx, name, description, use_user=use_user)
        self._first_speaker_name = None

    def _build_team_termination(self):
        return (
            PMCASwarmTermination(self._ctx).termination() | self._external_termination
        )

    async def _build_team_participants(self) -> None:
        """
        初始化 swarm 团队的参与智能体（ 视分诊结果决定 ）
        """
        self._participants = []

        triage_result = await self._ctx.task_workbench.get_item("triage_result")
        triage_team_list = triage_result.get("team")
        for team_item in triage_team_list:
            if team_item.get("name") == self._name:
                # 1. 获取本次 Swarm 的参与者名单
                participant_names = team_item.get("participants", [])

                # 如果名单为空，则此 Swarm 无需构建，直接跳出
                if not participant_names:
                    break

                # 2. 创建所有智能体实例
                for name in participant_names:
                    # 为每个智能体计算其 handoffs 列表，即名单中除自己外的所有人
                    # 这是实现“全连接”网络的关键
                    dynamic_handoffs = [
                        p_name for p_name in participant_names if p_name != name
                    ]

                    assistant = self._ctx.assistant_factory.create_assistant(
                        name, handoffs=dynamic_handoffs or None
                    )
                    self._participants.append(assistant)

                # 3. 将指定的“第一发言人”移动到列表的最前面
                # 分诊结果保证了 participants[0] 是第一发言人
                self._first_speaker_name = participant_names[0]

                try:
                    # 找到第一发言人的当前索引
                    speaker_index = next(
                        i
                        for i, p in enumerate(self._participants)
                        if p.name == self._first_speaker_name
                    )
                    # 将其移动到列表首位
                    first_speaker = self._participants.pop(speaker_index)
                    self._participants.insert(0, first_speaker)
                except StopIteration:
                    # 健壮性处理：如果因意外情况找不到指定的第一发言人，
                    # 列表将保持其初始顺序，第一个被创建的智能体将成为发言人。
                    logger.warning(
                        f"在 Swarm '{self._name}' 中未找到指定的第一发言人 '{self._first_speaker_name}'。"
                        "将使用默认顺序。"
                    )

                # 找到并处理完当前 Swarm 后，即可退出循环
                break

    def _build_team(self) -> Team:
        participants_list = [
            assistant
            for assistant in self._participants
            if isinstance(assistant, ChatAgent)
        ]
        return Swarm(
            participants=participants_list,
            name=self._name,
            description=self._description,
            termination_condition=self._termination,
        )
