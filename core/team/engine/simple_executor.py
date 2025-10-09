from typing import List
from autogen_agentchat.base import ChatAgent, Team
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
from loguru import logger
from base.runtime.task_context import PMCATaskContext
from core.team.common.team_messages import PMCARoutingMessages
from core.team.core_assistants import PMCACoreAssistants
from core.team.factory import PMCATeamFactory
from core.team.engine.termination import PMCATriageTermination


class PMCASimpleTaskTeam(PMCATeamFactory):
    def __init__(
        self,
        ctx: PMCATaskContext,
        name: str,
        description: str,
        use_user: bool = True,
    ) -> None:
        super().__init__(ctx, name, description, use_user=use_user)

    def _build_team_termination(self):
        return (
            PMCATriageTermination(self._ctx).termination() | self._external_termination  # type: ignore
        )

    async def _build_team_participants(self) -> None:
        """
        初始化分诊环节的参与智能体（ PMCATriage 和 PMCATriageReviewer ）
        """
        self._participants = []

        logger.info("进入构建简单任务候选列表环节")

        if not self._user_proxy:
            raise ValueError("[简单任务节点初始化阶段] 用户代理未能正常初始化")
        self._participants.append(self._user_proxy)

        triage_result = await self._ctx.task_workbench.get_item("triage_result")
        if triage_result.get("task_type") != "simple":
            raise ValueError(
                f"任务类型不匹配，simple 分支的 task_type 必须为 simple，当前类型为 {triage_result.get('task_type')}"
            )

        assistant_name = triage_result.get("assistant")
        assistant = self._ctx.assistant_factory.create_assistant(assistant_name)

        self._participants.append(assistant)

    def _build_team(self) -> Team:
        logger.info("【测试】：进入团队构建")
        return RoundRobinGroupChat(
            self._participants,
            name="PMCA-SIMPLE-TASK-EXECUTOR",
            description="简单任务执行器，负责处理用户简单任务的团队。",
            termination_condition=self._termination,
        )
