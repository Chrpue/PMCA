from typing import List, Literal
from autogen_agentchat.messages import BaseAgentEvent
from loguru import logger
from autogen_agentchat.base import ChatAgent, TaskResult, TerminationCondition
from autogen_agentchat.teams import Swarm
from autogen_agentchat.conditions import (
    TextMentionTermination,
    MaxMessageTermination,
    StopMessageTermination,
    TextMessageTermination,
)

from base.agents.factory import PMCAAgentFactory, PMCASpecialAgents
from base.agents.special_agents import PMCACodeGenExec, PMCACodeGenExecTool, PMCAUser
from base.team.factory import PMCATeam, TeamFeedBack


class PMCASwarm(PMCATeam):
    """Custom Swarm"""

    def termination(self) -> TerminationCondition:
        """设置群组的终止条件"""
        return (
            TextMentionTermination(TeamFeedBack.FINISHED)
            | TextMentionTermination(TeamFeedBack.NEEDUSER)
            | MaxMessageTermination(max_messages=80)
            | TextMentionTermination("APPROVE", sources="PMCAProxyUser")
            | self._external_termination
        )

    def create(self, participants):
        """构建Swarm群组"""

        # pmca_user_assistant = PMCAUser()

        # 团队成员名称与对象列表
        # participants_names = participants + [pmca_user_assistant.name]
        participants_names = participants
        participants_list: List[ChatAgent] = []

        # 初始化成员列表描述
        partners_desc = PMCAAgentFactory.list_partners_desc(participants)

        # 获取planner的提示词模板
        tpl = PMCAAgentFactory._registry["PMCASwarmPlanner"]
        tpl.system_message = tpl.system_message.format(partners=partners_desc)

        # logger.error("**********************************************")
        # logger.error(tpl.system_message)
        # logger.error("**********************************************")

        participants_list.append(
            self._factory.create_agent(
                "PMCASwarmPlanner",
                handoffs=participants_names,
                reflect_on_tool_use=False,
            )
        )

        # 配置团队参与任务的智能体对象列表
        for partner in participants:
            if partner not in PMCASpecialAgents:
                agent = self._factory.create_agent(
                    partner,
                    handoffs=["PMCASwarmPlanner"],
                    reflect_on_tool_use=False,
                )
                participants_list.append(agent)

            elif partner == "PMCACodeGenExec":
                team = PMCACodeGenExecTool(model_client=self._model_client)
                self._executor = team.docker_exec

                agent = self._factory.create_agent(
                    partner,
                    handoffs=["PMCASwarmPlanner"],
                    tools=[team.team_tool],
                    reflect_on_tool_use=True,
                )
                participants_list.append(agent)

        # participants_list.append(PMCAUser().agent)

        # logger.error("**********************************************")
        # logger.error(participants)
        # logger.error("**********************************************")

        return Swarm(
            participants_list,
            termination_condition=self._termination,
        )
