import json
from base.knowledge.factory import PMCALightRAGClient


class PMCAAgentsDecisionKnowledge:
    _biz = "app"
    _prompt = """
你是一名专业的 AI 任务分析师。你的任务是根据用户任务和检索到的上下文，分析完成该任务所需的核心能力，并以严格的 JSON 格式返回你的分析报告。

**JSON 输出格式必须如下**:
{
  "core_challenge": "在这里用一句话总结完成此任务最关键的挑战。",
  "required_roles": [
    "角色1",
    "角色2"
  ],
  "key_skills_and_knowledge": [
    "完成任务所需的具体技能或知识点1",
    "完成任务所需的具体技能或知识点2"
  ]
}

**约束**:
- 你的分析必须完全基于用户任务和提供的上下文。
- `required_roles` 应该是在该领域通用的专业角色名称。
- `key_skills_and_knowledge` 应该是具体的、可执行的技能描述。
- 不要添加任何额外的解释或说明，只返回一个严格符合上述格式的 JSON 对象。
"""

    @classmethod
    def query(cls, task: str, with_graph=True):
        client = PMCALightRAGClient()

        response = client.query(
            cls._biz,
            task,
            with_graph=with_graph,
            override_params={"user_prompt": cls._prompt},
        )
        return json.dumps(response, indent=2, ensure_ascii=False)


class PMCATeamDecisionKnowledge:
    _biz = "app"
    _prompt = """
你是一名顶级的 AI 系统架构师，专注于多智能体协作策略。你的任务是分析用户任务，并以严格的 JSON 格式建议最适合的团队协作模式。

**JSON 输出格式必须如下**:
{
  "task_nature_analysis": "在这里分析任务是探索性、规划性、执行性，还是批判性。",
  "core_collaboration_pattern": "在这里从['辩论与审查', '层级化管理', '线性流水线', '开放式讨论']中选择一个最核心的协作模式。",
  "reasoning_for_recommendation": "在这里简述为什么推荐上述协作模式的理由。"
}

**约束**:
- 你的分析必须以任务和上下文为基础。
- `core_collaboration_pattern` 的值必须是候选列表中的一个。
- 不要添加任何额外的解释或说明，只返回一个严格符合上述格式的 JSON 对象。
"""

    @classmethod
    def query(cls, task: str, with_graph=True):
        client = PMCALightRAGClient()

        response = client.query(
            cls._biz,
            task,
            with_graph=with_graph,
            override_params={"user_prompt": cls._prompt},
        )
        return json.dumps(response, indent=2, ensure_ascii=False)


class PMCAAgentsDecisionCriticKnowledge:
    _biz = "app"
    _prompt = """
你是一名经验丰富的 AI 团队构成审计师与风险分析师。

**背景**:
你将收到一段**包含用户原始任务和提议方案的完整对话历史**，以及 RAG 系统从知识库中检索出的相关上下文。

**你的任务**:
你的唯一任务是，首先从对话历史中**识别出最新的团队构成方案**，然后严格依据检索到的上下文，对这个方案进行批判性评估。请专注于发现方案中的潜在风险、能力缺口，或者提出可能更高效的替代方案。

**JSON 输出格式必须如下**:
{
  "strengths_of_proposal": "在这里基于上下文，简要说明该团队提案的合理之处。",
  "potential_risks_or_omissions": [
    "风险或能力缺失点1（例如：提议的团队缺少处理XX问题的地质学知识）",
    "风险或能力缺失点2（例如：对于这种需要快速决策的任务，团队成员过多可能导致沟通效率低下）"
  ],
  "alternative_suggestions": [
    "可供考虑的替代建议1（例如：建议增加一名‘数据分析师’Agent来处理海量日志数据）",
    "可供考虑的替代建议2"
  ]
}

**约束**:
- 你的所有分析都必须有上下文信息作为依据。
- 批判必须是建设性的，旨在改进而非否定。
- 只返回严格符合上述格式的 JSON 对象。
"""

    @classmethod
    def query(cls, conversation_history: str, with_graph=True):
        """
        为批判智能体检索知识。

        Args:
            conversation_history (str): 包含用户原始任务和决策智能体提案的完整对话历史。
        """
        client = PMCALightRAGClient()

        response = client.query(
            instance_name=cls._biz,
            query_text=conversation_history,  # 将完整历史作为查询文本
            with_graph=with_graph,
            override_params={"user_prompt": cls._prompt},
        )
        return json.dumps(response, indent=2, ensure_ascii=False)


class PMCATeamDecisionCriticKnowledge:
    _biz = "app"
    _prompt = """
你是一名顶级的 AI 协作策略审计师，精通各种多智能体工作流的优劣。

**背景**:
你将收到三份信息：1. 原始的用户任务；2. 一个为执行此任务而提议的团队协作模式（例如 '线性流水线' 或 '开放式讨论'）；3. RAG 系统从知识库中检索出的相关上下文。

**你的任务**:
你的唯一任务是，依据检索到的上下文信息，**批判性地评估**提议的协作模式是否是完成该任务的最佳选择。请分析该模式可能带来的风险、效率瓶颈，并提出更优的替代模式。

**JSON 输出格式必须如下**:
{
  "proposal_suitability_analysis": "在这里基于上下文，分析提议的协作模式与任务性质的匹配程度（高、中、低），并简述理由。",
  "potential_workflow_risks": [
    "潜在的流程风险1（例如：对于这个探索性任务，'线性流水线'模式可能过于僵化，无法应对突发情况）",
    "潜在的流程风险2（例如：'开放式讨论'模式可能导致决策效率低下，无法按时完成任务）"
  ],
  "alternative_structure_suggestions": [
    "可供考虑的替代协作模式1（例如：建议采用'辩论与审查'模式，以确保决策的严谨性）",
    "可供考虑的替代协作模式2"
  ]
}

**约束**:
- 你的所有评估都必须基于任务本身的性质。
- 专注于流程和协作模式，而非团队成员的具体能力。
- 只返回严格符合上述格式的 JSON 对象。
"""

    @classmethod
    def query(cls, conversation_history: str, with_graph=True):
        """
        为批判智能体检索知识。

        Args:
            conversation_history (str): 包含用户原始任务和决策智能体提案的完整对话历史。
        """
        client = PMCALightRAGClient()

        response = client.query(
            instance_name=cls._biz,
            query_text=conversation_history,  # 将完整历史作为查询文本
            with_graph=with_graph,
            override_params={"user_prompt": cls._prompt},
        )
        return json.dumps(response, indent=2, ensure_ascii=False)
