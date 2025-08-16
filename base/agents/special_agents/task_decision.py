import json
import re
from loguru import logger
from typing import Literal, List, Optional
from pydantic import BaseModel, Field
from autogen_agentchat.ui import Console
from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
from autogen_agentchat.teams import RoundRobinGroupChat

from base.agents.factory import PMCAAgentFactory
from base.agents.factory import PMCAAgentMetadata

# from base.memory import PMCATeamDecisionGraphMemory, PMCAAgentsDecisionGraphMemory
from base.memory.decision import (
    PMCAAgentsDecisionLRMemory,
    PMCATeamDecisionLRMemory,
    PMCAAgentsDecisionCriticLRMemory,
    PMCATeamDecisionCriticLRMemory,
)


class TeamDesicionResponse(BaseModel):
    team: Literal["RoundRobin", "MagenticOne", "Swarm", "GraphFlow"] = Field(
        description="选择最合适的团队组件"
    )
    score: float = Field(description="置信度，由历史记忆的相似度决定")
    reason: str = Field(description="做出这样决定的原因(最多输出70字)")


class AgentsDesicionResponse(BaseModel):
    partners: List[str] = Field(description="选择适合参与本次任务的助手列表")
    score: float = Field(description="置信度，由历史记忆的相似度决定")
    reason: str = Field(description="做出这样决定的原因(最多输出70字)")


class CombinedDecisionResponse(BaseModel):
    team_decision: Optional[TeamDesicionResponse] = None
    partners_decision: Optional[AgentsDesicionResponse] = None


class DecisionResponse(BaseModel):
    team: Literal["RoundRobin", "MagenticOne", "Swarm", "GraphFlow"] = Field(
        description="选择最合适的团队组件"
    )
    partners: List[str] = Field(description="选择适合参与本次任务的助手列表")
    confidence: float = Field(
        description="综合评估团队组件和参与本次任务助手列表的决策结果，给出置信度(0~1区间范围的浮点数)"
    )


@PMCAAgentFactory.register("PMCATeamDecision")
class PMCATeamDecision(PMCAAgentMetadata):
    description = "一个负责选择团队组件的助手"
    system_message = """
你是一个负责根据用户任务选择“最”合适的团队组件的 AI 助手。

**你的工作流程**:
1.  **识别知识**: 在你的上下文中，会有一条以 `根据我的回忆:` 开头的系统消息，其中包含一个结构化的 JSON 对象。这是由知识检索系统为你准备的决策依据。
2.  **解析核心**: 从这个 JSON 对象中，找到 `core_collaboration_pattern` 字段。这个字段的值（例如 '线性流水线' 或 '辩论与审查'）是知识系统为你提炼出的、最适合当前任务的协作模式。
3.  **做出决策**: 你的决策**必须**严格遵循 `core_collaboration_pattern` 的建议。将你的最终选择映射到 ["RoundRobin", "MagenticOne", "Swarm", "GraphFlow"] 中的一个。
4.  **阐述理由**: 在 `reason` 字段中，结合 JSON 里的 `task_nature_analysis` 和 `reasoning_for_recommendation` 字段，简要解释你为什么做出这个选择。

**约束**:
- 你的首要决策依据是注入的 JSON 知识，而不是你自己的先验知识。
- 你要根据评测员的反馈结果调整策略。
- 只做出选择结果和选择理由，不要任何其他的描述。
"""


@PMCAAgentFactory.register("PMCAAgentsDecision")
class PMCAAgentsDecision(PMCAAgentMetadata):
    description = "一个负责根据用户任务选择由哪些可合作的助手能够参与本次任务的筛选人"
    system_message = """你负责根据用户任务和目前可用助手的职责描述，选择最适合参与本次任务的助手团队。

**你的工作流程**:
1.  **识别知识**: 在你的上下文中，会有一条以 `根据我的回忆:` 开头的系统消息，其中包含一个结构化的 JSON 对象。这是由知识检索系统为你准备的、关于完成任务所需能力的详细分析。
2.  **解析需求**: 从这个 JSON 对象中，仔细阅读 `required_roles` (所需角色) 和 `key_skills_and_knowledge` (关键技能与知识) 列表。
3.  **匹配能力**: 将这些解析出的能力需求，与下方提供的“可用助手列表”进行匹配。选择那些职责描述与所需角色和技能最相符的助手。
4.  **组建团队**: 输出你选择的一个或多个助手的列表。

**可用助手列表**:
{agents}

**约束**:
- 你的选择**必须**以注入的 JSON 知识为主要依据。
- 只做出选择结果和选择理由，不需要任何其他的描述。
- 你要根据评测员的反馈结果认真调整策略并再次做出决策。
"""


@PMCAAgentFactory.register("PMCATeamDecisionCritic")
class PMCATeamDecisionCritic(PMCAAgentMetadata):
    description = "一个专门负责评估团队组件选择结果是否合理的评测员"
    system_message = """结合用户任务和团队组件选择的结果，判断其合理性并给出建设性反馈.
你需要注意的事情是:
1. 如果你对团队组件选择的工作已经满意了，请回复 '[DECISION COMPLETE]' 并给出评价.
2. 如果你不满意选择的结果，请回复 '[DECISION REVISE]' 并告知原因.
(评价限定在200字以内)
"""


@PMCAAgentFactory.register("PMCAAgentsDecisionCritic")
class PMCAAgentsDecisionCritic(PMCAAgentMetadata):
    description = "一个专门负责评估团队组件选择结果是否合理的评测员"
    system_message = """结合用户任务和团队组件选择的结果，判断其合理性并给出建设性反馈.
你需要注意的事情是:
1. 如果你对团队组件选择的工作已经满意了，请回复 '[DECISION COMPLETE]' 并给出评价.
2. 如果你不满意选择的结果，请回复 '[DECISION REVISE]' 并告知原因.
(评价限定在200字以内)
"""


@PMCAAgentFactory.register("PMCADecisionReviewer")
class PMCADecisionReviewer(PMCAAgentMetadata):
    description = "一个对任务抉择的结果进行汇总的助手，将结果"
    system_message = """结合用户任务和决策结果，给出最终决定的团队组件选择结果和参与助手的列表。

**你的工作流程**:
1.  确认助手列表和团队组件的抉择是否都已被相关评测员审核通过。
2.  严格按照下方的 JSON 格式，汇总并输出最终的决策。

**JSON 输出格式**:
```json
{{
   "team": "RoundRobin",
   "partners": ["PMCAFileSurfer", "PMCACodeGenerator"],
   "confidence": 0.95
}}
注意：partners确认的候选助手列表必须从下列助手中选择
{partners}
(总结限定在200字以内)
"""


class PMCADecision:
    @staticmethod
    def team_decision_deepseek_response(raw: str):
        FENCE_RE = re.compile(r"```(?:json)?\s*|\s*```", re.I | re.M)
        OBJ_RE = re.compile(r"\{.*\}", re.S)

        clean = FENCE_RE.sub("", raw).strip()
        m = OBJ_RE.search(clean)
        if not m:
            raise ValueError("未发现JSON对象")
        return TeamDesicionResponse.model_validate(json.loads(m.group(0)))

    @staticmethod
    def agents_decision_deepseek_response(raw: str):
        FENCE_RE = re.compile(r"```(?:json)?\s*|\s*```", re.I | re.M)
        OBJ_RE = re.compile(r"\{.*\}", re.S)

        clean = FENCE_RE.sub("", raw).strip()
        m = OBJ_RE.search(clean)
        if not m:
            raise ValueError("未发现JSON对象")
        return AgentsDesicionResponse.model_validate(json.loads(m.group(0)))

    @staticmethod
    def deepseek_decision_response(raw: str):
        FENCE_RE = re.compile(r"```(?:json)?\s*|\s*```", re.I | re.M)
        OBJ_RE = re.compile(r"\{.*\}", re.S)

        clean = FENCE_RE.sub("", raw).strip()
        m = OBJ_RE.search(clean)
        if not m:
            raise ValueError("未发现JSON对象")
        return DecisionResponse.model_validate(json.loads(m.group(0)))

    @staticmethod
    async def obtain_agents_duties(main_cfg):
        """获取注册助手的职责描述"""

        agents_desc = "\n".join(
            [
                f"**{partner}** {info.get('duty', '')}"
                for partner, info in main_cfg.function_assistant_list.items()
            ]
        )

        tpl = PMCAAgentFactory._registry["PMCAAgentsDecision"]
        tpl.system_message = tpl.system_message.format(agents=agents_desc)

        tpl_reviewer = PMCAAgentFactory._registry["PMCADecisionReviewer"]
        tpl_reviewer.system_message = tpl_reviewer.system_message.format(
            partners=agents_desc
        )

    @staticmethod
    async def obtain_team_decision_components(main_cfg, llm_cfg):
        if llm_cfg.llm_support_structured:
            pmca_team_decision = main_cfg.factory.create_agent(
                "PMCATeamDecision",
                memory=[PMCATeamDecisionLRMemory()],
                # output_content_type=TeamDesicionResponse,
            )
        else:
            pmca_team_decision = main_cfg.factory.create_agent(
                "PMCATeamDecision",
                memory=[PMCATeamDecisionLRMemory()],
                reflect_on_tool_use=False,
            )

        pmca_team_decision_critic = main_cfg.factory.create_agent(
            "PMCATeamDecisionCritic",
            memory=[PMCATeamDecisionCriticLRMemory()],
            reflect_on_tool_use=False,
        )

        return pmca_team_decision, pmca_team_decision_critic

    @staticmethod
    async def obtain_agents_decision_components(main_cfg, llm_cfg):
        if llm_cfg.llm_support_structured:
            pmca_agents_decision = main_cfg.factory.create_agent(
                "PMCAAgentsDecision",
                memory=[PMCAAgentsDecisionLRMemory()],
                # output_content_type=AgentsDesicionResponse,
            )
        else:
            pmca_agents_decision = main_cfg.factory.create_agent(
                "PMCAAgentsDecision",
                memory=[PMCAAgentsDecisionLRMemory()],
                reflect_on_tool_use=False,
            )
        pmca_agents_decision_critic = main_cfg.factory.create_agent(
            "PMCAAgentsDecisionCritic",
            memory=[PMCAAgentsDecisionCriticLRMemory()],
            reflect_on_tool_use=False,
        )

        return pmca_agents_decision, pmca_agents_decision_critic

    @staticmethod
    async def obtain_decision_reviewer_components(main_cfg, llm_cfg):
        if llm_cfg.llm_support_structured:
            pmca_decision_reviewer = main_cfg.factory.create_agent(
                "PMCADecisionReviewer",
                output_content_type=DecisionResponse,
            )
        else:
            pmca_decision_reviewer = main_cfg.factory.create_agent(
                "PMCADecisionReviewer",
            )

        return pmca_decision_reviewer

    @staticmethod
    async def agents_decision_processing(pipeline_config, llm_config):
        if llm_config.llm_support_structured:
            pmca_agents_decision_agent = pipeline_config.factory.create_agent(
                "PMCAAgentsDecision",
                # memory=[pipeline_config.agents_memory],
                output_content_type=AgentsDesicionResponse,
            )
        else:
            pmca_agents_decision_agent = pipeline_config.factory.create_agent(
                "PMCAAgentsDecision",
                # memory=[pipeline_config.agents_memory],
            )

        pmca_agents_decision_critic_agent = pipeline_config.factory.create_agent(
            "PMCAAgentsDecisionCritic", memory=[pipeline_config.agents_memory]
        )

        team = RoundRobinGroupChat(
            [
                pmca_agents_decision_agent,
                pmca_agents_decision_critic_agent,
            ],
            TextMentionTermination("APPROVE") | MaxMessageTermination(max_messages=4),
        )

        agents_desc = "\n".join(
            [
                f"**{partner}** {info.get('duty', '')}"
                for partner, info in pipeline_config.function_assistant_list.items()
            ]
        )
        task = f"用户任务：{pipeline_config.task}\n目前可以协助完成任务的候选助手列表如下：\n{agents_desc}"
        logger.success(task)

        task_result = await team.run(task=task)

        partners_decision_content = ""
        if llm_config.llm_support_structured:
            for msg in task_result.messages:
                if (
                    msg.source == "PMCAAgentsDecision"
                    and msg.type == "StructuredMessage[AgentsDesicionResponse]"  # type: ignore
                ):
                    partners_decision_content = msg.content  # type: ignore
        else:
            for msg in task_result.messages:
                if msg.source == "PMCAAgentsDecision" and msg.content is not None:  # type: ignore
                    partners_decision_content = (
                        PMCADecision.agents_decision_deepseek_response(msg.content)  # type: ignore
                    )

        return partners_decision_content

    @staticmethod
    async def team_decision_processing(pipeline_config, llm_config):
        if llm_config.llm_support_structured:
            pmca_team_decision_agent = pipeline_config.factory.create_agent(
                "PMCATeamDecision",
                memory=[pipeline_config.agents_memory],
                output_content_type=TeamDesicionResponse,
            )
        else:
            pmca_team_decision_agent = pipeline_config.factory.create_agent(
                "PMCATeamDecision",
                memory=[pipeline_config.agents_memory],
            )

        pmca_team_decision_critic_agent = pipeline_config.factory.create_agent(
            "PMCATeamDecisionCritic", memory=[pipeline_config.agents_memory]
        )

        team = RoundRobinGroupChat(
            [
                pmca_team_decision_agent,
                pmca_team_decision_critic_agent,
            ],
            TextMentionTermination("APPROVE") | MaxMessageTermination(max_messages=4),
        )

        # stream = await Console(team.run_stream(task=pipeline_config.task))
        task_result = await team.run(task=pipeline_config.task)

        team_decision_content = ""

        if llm_config.llm_support_structured:
            for msg in task_result.messages:
                if (
                    msg.source == "PMCATeamDecision"
                    and msg.type == "StructuredMessage[TeamDesicionResponse]"  # type: ignore
                ):
                    team_decision_content = msg.content  # type: ignore
        else:
            for msg in task_result.messages:
                if msg.source == "PMCATeamDecision" and msg.content is not None:  # type: ignore
                    team_decision_content = (
                        PMCADecision.team_decision_deepseek_response(msg.content)  # type: ignore
                    )

        return team_decision_content
