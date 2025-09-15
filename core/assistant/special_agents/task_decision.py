import json
import re
from loguru import logger
from typing import Literal, List, Optional
from pydantic import BaseModel, Field
from autogen_agentchat.ui import Console
from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
from autogen_agentchat.teams import RoundRobinGroupChat

from base.configs import PMCASystemEnvConfig
from base.runtime import PMCATaskContext
from core.assistant.factory import PMCAAssistantFactory
from core.assistant.factory import PMCAAssistantMetadata
from core.client.llm_factory import ProviderType


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


@PMCAAssistantFactory.register("PMCATeamDecision")
class PMCATeamDecision(PMCAAssistantMetadata):
    description = "一个负责选择团队组件的助手"
    system_message = """
你是一位顶级的“多智能体协作策略师”，你的任务是为给定的用户任务，选择最合适的团队协作模式。

**背景知识：可用的团队协作模式 (你必须从中选择一种)**:
- **'RoundRobin'**: 适用于**步骤固定、流程简单**的任务。智能体按预定顺序依次发言，像工厂流水线一样。
- **'Swarm'**: 适用于**需要动态规划和局部决策**的任务。智能体之间可以灵活地“传递”任务，不需要中心化的管理者。
- **'GraphFlow'**: 适用于**流程复杂、有明确依赖关系**（如条件分支、并行、循环）并需要稳定复现的任务。你需要预先定义好一张流程图。
- **'MagenticOne'**: 适用于**需要与外部世界（网页、文件系统）交互**的复杂、开放性问题。它自带一个“协调员”来统一规划和分配任务。

**你的任务**:
1.  分析用户任务的核心需求。
2.  结合上述背景知识，判断哪种协作模式最匹配。
3.  严格按照下面的JSON格式输出你的决策。

**JSON 输出格式（必须严格遵守）**:
```json
{{
    "team": "（必须是 'RoundRobin', 'MagenticOne', 'Swarm', 'GraphFlow' 中的一个）",
    "score": 0.9,
    "reason": "（根据任务性质和协作模式的特点，详细阐述你做出选择的原因，限70字以内）"
}}
**约束**:
- `team` 的值必须是候选列表中的一个。
- 你的所有分析都必须基于用户任务和上下文。
- 绝对不要在JSON之外添加任何额外的解释、注释或问候语。
"""


@PMCAAssistantFactory.register("PMCAAgentsDecision")
class PMCAAgentsDecision(PMCAAssistantMetadata):
    description = "一个负责根据用户任务选择由哪些可合作的助手能够参与本次任务的筛选人"
    system_message = """你是一位顶级的AI智能体团队“首席任务官”（Chief Task Officer）。你的核心职责是深刻理解用户下达的任务，并结合我们知识库中检索到的“历史智慧”（上下文），精准地规划出完成任务所需的角色和核心能力。

**可用的团队成员与能力**
{agents}

**思考流程**:
1.  **任务拆解**: 首先，仔细分析用户下达的核心任务目标是什么。
2.  **智慧融合**: 然后，阅读提供给你的“上下文信息”，这些信息是我们过往成功案例和知识沉淀。你必须将这些信息作为你决策的首要依据。
3.  **能力映射**: 最后，基于任务和历史智慧，推导出完成此任务最关键的挑战是什么，需要哪些通用的专业角色，以及这些角色必须具备的特定技能。

**JSON 输出格式（必须严格遵守）**:
{{
    "partners": [
        "（智能体1的英文名，必须来自候选列表）",
        "（智能体2的英文名，必须来自候选列表）"
    ],
    "score": 0.9,
    "reason": "（解释你为什么选择这几位智能体，它们如何协同工作来完成任务，限70字以内）"
}}

**约束**:
- 列表中的所有智能体名称，都必须从上面提供的“候选智能体列表”中选择，禁止凭空捏造。
- 你的所有分析都必须基于用户任务和候选智能体的职责描述。
- 绝对不要在JSON之外添加任何额外的解释、注释或问候语。
"""


@PMCAAssistantFactory.register("PMCATeamDecisionCritic")
class PMCATeamDecisionCritic(PMCAAssistantMetadata):
    description = "一个专门负责评估团队组件选择结果是否合理的评测员"
    system_message = """你是一位顶级的AI协作流程审计师，对多智能体工作流的效率和风险有深刻的洞察。

**输入信息**:
你将收到两部分信息：
1.  **对话历史**: 你将收到包含用户任务和一个初步团队协作模式提案的对话历史。。
2.  **参考知识**: RAG系统从知识库中检索到的、与该任务相关的上下文。

**核心任务**:
你的任务是严格评估提案中的协作模式是否是完成该任务的最佳选择。

你的回应格式:
- 如果你满意该提案，请只回复一行：[TEAM DECISION COMPLETE]。并在后面附上你的简短评价。
- 如果你不满意该提案，请只回复一行：[TEAM DECISION REVISE]。并在后面附上你认为需要修正的原因和建议。

示例（满意时）:
[TEAM DECISION COMPLETE]
评价：该任务步骤清晰，前后依赖性强，选择'GraphFlow'模式非常合理，能够保证流程的稳定性和效率。

示例（不满意时）:
[TEAM DECISION REVISE]
原因：该任务具有高度的不确定性和探索性，使用'GraphFlow'这种固定流程的模式过于僵化，建议改为'Swarm'模式，以允许智能体之间进行更灵活的动态协作。

(评价限定在200字以内)
"""


@PMCAAssistantFactory.register("PMCAAgentsDecisionCritic")
class PMCAAgentsDecisionCritic(PMCAAssistantMetadata):
    description = "一个专门负责评估团队组件选择结果是否合理的评测员"
    system_message = """你是一名资深的AI团队构成审计师，以挑剔和建设性的眼光著称。

**输入信息**:
你将收到两部分信息：
1.  **对话历史**: 你将收到包含用户任务和一个初步智能体团队构成方案的对话历史。。
2.  **参考知识**: RAG系统从知识库中检索到的、与该任务相关的上下文。

**核心任务**:
你的唯一任务是严格评估这个团队构成方案是否合理、高效。

你的回应格式:
- 如果你满意该团队构成，请只回复一行：[AGENTS DECISION COMPLETE]。并在后面附上你的简短评价。
- 如果你不满意该团队构成，请只回复一行：[AGENTS DECISION REVISE]。并在后面附上你认为需要修正的原因和建议。

示例（满意时）:
[AGENTS DECISION COMPLETE]
评价：选择的'代码工程师'和'测试工程师'组合非常经典，完全覆盖了任务从开发到测试的全流程，职责清晰。

示例（不满意时）:
[AGENTS DECISION REVISE]
原因：任务中明确提到了需要进行数据可视化，但团队中缺少'数据分析师'角色，仅靠'代码工程师'可能无法制作出专业的图表，建议增补。

**约束**:
- 你的每一条评估和建议，都必须能从“参考知识”中找到直接或间接的支撑，如果你并没有在知识库中索引到相关反例，请不要做出否定的建议。
(评价限定在200字以内)
"""


@PMCAAssistantFactory.register("PMCADecisionReviewer")
class PMCADecisionReviewer(PMCAAssistantMetadata):
    description = "一个对任务抉择的结果进行汇总的助手，将结果"
    system_message = """你是“最终决策审查官”，负责在所有决策环节都完成后，进行最终的确认和汇总。

**你的工作流程**:
1.  **审查历史**: 仔细审查整个对话历史记录。
2.  **执行操作**:
    - **如果两个批准信号都存在**: 你必须首先严格按照下方的 JSON 格式，汇总并输出最终的决策。然后，在JSON之后，必须紧接着另起一行，输出最终的终止指令：`[OVERALL DECISION COMPLETE]`。
    - **如果缺少任何一个批准信号**: 你必须回复：“决策流程尚未完全批准，我将等待团队组件和智能体成员的决策都通过审核。”

**JSON 输出格式**:
```json
{{
   "team": "RoundRobin",
   "partners": ["PMCAFileSurfer", "PMCACodeGenerator"],
   "confidence": 0.95
}}
**约束**
- partners确认的候选助手列表必须从下列助手中选择
{partners}
- 只有在确认两个独立的批准信号后，才能输出JSON和最终终止指令。
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

        logger.success("\n" + agents_desc)

        if (
            "{agents}"
            in PMCAAgentFactory._registry["PMCAAgentsDecision"].system_message
        ):
            tpl = PMCAAgentFactory._registry["PMCAAgentsDecision"]
            tpl.system_message = tpl.system_message.format(agents=agents_desc)

        if (
            "{partners}"
            in PMCAAgentFactory._registry["PMCADecisionReviewer"].system_message
        ):
            tpl_reviewer = PMCAAgentFactory._registry["PMCADecisionReviewer"]
            tpl_reviewer.system_message = tpl_reviewer.system_message.format(
                partners=list(main_cfg.function_assistant_list.keys())
            )

    @staticmethod
    async def obtain_team_decision_components(task_ctx: PMCATaskContext):
        if task_ctx.llm_factory.supports_structured(
            ProviderType(task_ctx.task_model_provider), task_ctx.task_model_name
        ):
            pmca_team_decision = task_ctx.agent_factory.create_agent(
                "PMCATeamDecision",
            )
        else:
            pmca_team_decision = task_ctx.agent_factory.create_agent(
                "PMCATeamDecision",
                reflect_on_tool_use=False,
            )

        pmca_team_decision_critic = task_ctx.agent_factory.create_agent(
            "PMCATeamDecisionCritic",
            reflect_on_tool_use=False,
        )

        return pmca_team_decision, pmca_team_decision_critic

    @staticmethod
    async def obtain_agents_decision_components(task_ctx: PMCATaskContext):
        if task_ctx.llm_factory.supports_structured(
            ProviderType(task_ctx.task_model_provider), task_ctx.task_model_name
        ):
            pmca_agents_decision = task_ctx.agent_factory.create_agent(
                "PMCAAgentsDecision",
                output_content_type=AgentsDesicionResponse,
            )
        else:
            pmca_agents_decision = task_ctx.agent_factory.create_agent(
                "PMCAAgentsDecision",
                reflect_on_tool_use=False,
            )
        pmca_agents_decision_critic = task_ctx.agent_factory.create_agent(
            "PMCAAgentsDecisionCritic",
            reflect_on_tool_use=False,
        )

        return pmca_agents_decision, pmca_agents_decision_critic

    @staticmethod
    async def obtain_decision_reviewer_components(task_ctx: PMCATaskContext):
        if task_ctx.llm_factory.supports_structured(
            ProviderType(task_ctx.task_model_provider), task_ctx.task_model_name
        ):
            pmca_decision_reviewer = task_ctx.agent_factory.create_agent(
                "PMCADecisionReviewer",
                output_content_type=DecisionResponse,
            )
        else:
            pmca_decision_reviewer = task_ctx.agent_factory.create_agent(
                "PMCADecisionReviewer",
            )

        return pmca_decision_reviewer

    @staticmethod
    async def agents_decision_processing(task_ctx: PMCATaskContext):
        team = RoundRobinGroupChat(
            list(await PMCADecision.obtain_agents_decision_components(task_ctx)),
            MaxMessageTermination(max_messages=34),  # type: ignore
        )

        agents_desc = "\n".join(
            [
                f"**{partner}** {info.get('duty', '')}"
                for partner, info in task_ctx.agent_factory.list_functional_agents().items()
            ]
        )
        task = f"用户任务：{task_ctx.task_mission}\n目前可以协助完成任务的候选助手列表如下：\n{agents_desc}"
        logger.success(task)

        task_result = await team.run(task=task)

        partners_decision_content = ""
        if task_ctx.llm_factory.supports_structured(
            ProviderType(task_ctx.task_model_provider), task_ctx.task_model_name
        ):
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
    async def team_decision_processing(task_ctx: PMCATaskContext):
        team = RoundRobinGroupChat(
            list(await PMCADecision.obtain_team_decision_components(task_ctx)),
            MaxMessageTermination(max_messages=34),  # type: ignore
        )

        # stream = await Console(team.run_stream(task=pipeline_config.task))
        task_result = await team.run(task=task_ctx.task_mission)

        team_decision_content = ""

        if task_ctx.llm_factory.supports_structured(
            ProviderType(task_ctx.task_model_provider), task_ctx.task_model_name
        ):
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
