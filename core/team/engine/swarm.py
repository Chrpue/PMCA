from typing import List
from loguru import logger
from autogen_agentchat.base import ChatAgent, Team
from autogen_agentchat.teams import RoundRobinGroupChat, Swarm
from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
from base.runtime.task_context import PMCATaskContext
from core.team.common.team_messages import PMCARoutingMessages
from core.team.core_assistants import PMCACoreAssistants
from core.team.factory import PMCATeamFactory


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

    def _team_text_termination(self) -> List[TextMentionTermination]:
        """
        初始化分诊环节的终止信号（条件）
        """
        return [
            TextMentionTermination(item.value)
            for item in PMCARoutingMessages.swarm_termination()
        ]

    def _team_max_turns(self) -> MaxMessageTermination:
        """
        初始化分诊环节的最大轮询次数（环境变量提供）
        """
        return MaxMessageTermination(self._ctx.task_env.SWARM_MAX_TURNS)

    async def _build_team_participants(self) -> None:
        """
        初始化 swarm 团队的参与智能体（ 视分诊结果决定 ）
        """
        self._participants = []

        triage_result = await self._ctx.task_workbench.get_item("triage_result")
        triage_team_list = triage_result.get("team")
        # for team_item in triage_team_list:
        #     if team_item.get("name") == self._name:
        #         swarm_participants = team_item.get("participants")
        #         self._first_speaker_name = swarm_participants[0]
        #         for name in swarm_participants:
        #             dynamic_handoffs = [
        #                 p_name for p_name in swarm_participants if p_name != name
        #             ]
        #             assistant = self._ctx.assistant_factory.create_assistant(
        #                 name, dynamic_hadoffs=dynamic_handoffs or None
        #             )
        #             self._participants.append(assistant)
        #         break
        #
        # first_speaker = next(
        #     p for p in self._participants if p.name == self._first_speaker_name
        # )
        #
        # self._participants.remove(first_speaker)
        # self._participants.insert(0, first_speaker)
        #
        # self._participants.append(
        #     self._ctx.assistant_factory.create_assistant(
        #         PMCACoreAssistants.SWARM_SUPERVISOR.value
        #     )
        # )
        #
        # self._participants

        supervisor_name = PMCACoreAssistants.SWARM_SUPERVISOR.value

        for team_item in triage_team_list:
            if team_item.get("name") == self._name:
                # 1. 获取本 Swarm 的专家智能体名单
                expert_participant_names = team_item.get("participants", [])
                if not expert_participant_names:
                    continue

                # 2. 创建所有专家智能体 (Spokes)
                for name in expert_participant_names:
                    # 专家的 handoffs 列表只包含监督者
                    expert_handoffs = [supervisor_name]

                    logger.info(f"目标智能体：{name}，Handoffs：{expert_handoffs}")

                    assistant = self._ctx.assistant_factory.create_assistant(
                        name, handoffs=expert_handoffs
                    )
                    self._participants.append(assistant)

                # 3. 创建监督者智能体 (Hub)
                # 监督者的 handoffs 列表包含所有专家
                supervisor_handoffs = expert_participant_names

                logger.info(
                    f"目标智能体：{supervisor_name}，Handoffs：{supervisor_handoffs}"
                )

                supervisor_assistant = self._ctx.assistant_factory.create_assistant(
                    supervisor_name, handoffs=supervisor_handoffs
                )
                # 将监督者添加到列表末尾
                self._participants.append(supervisor_assistant)

                # 4. 确保指定的 first_speaker 在列表的第一个位置
                self._first_speaker_name = expert_participant_names[0]
                try:
                    first_speaker_index = next(
                        i
                        for i, p in enumerate(self._participants)
                        if p.name == self._first_speaker_name
                    )
                    first_speaker = self._participants.pop(first_speaker_index)
                    self._participants.insert(0, first_speaker)
                except StopIteration:
                    pass

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
