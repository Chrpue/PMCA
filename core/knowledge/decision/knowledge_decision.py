import json
from typing import Optional, Dict
from core.knowledge.factory import PMCALightRAGClient


class PMCAKnowledge:
    # _format_context 保持 @staticmethod 不变
    @staticmethod
    def _format_context(query_result: Optional[Dict]) -> str:
        if not query_result or not query_result.get("chunks"):
            return "在知识库中未检索到相关信息。"

        context_str = "\n\n".join(
            [
                f"参考知识 {i + 1}:\n{chunk.get('text', '')}"
                for i, chunk in enumerate(query_result["chunks"])
            ]
        )
        # **优化**: 在最终交付给LLM的上下文中，可以移除我们的内部标记，使其更干净
        context_str = context_str.replace(
            "[KnowledgeFor: PMCATeamDecision]", ""
        ).replace("[KnowledgeFor: PMCAAgentsDecision]", "")  # 未来可以扩展
        return f"为你检索到如下参考知识：\n{context_str}"


class PMCAAgentsDecisionKnowledge(PMCAKnowledge):
    _biz = "app"
    _prompt = """
作为一名顶级的AI智能体团队“首席任务官”，我的任务是基于给定的“当前任务”和知识库中的“相关历史知识”，为外部的“智能体决策官”精准地定义出所需的【理想团队画像】。

**我的分析流程**:
1.  **需求分解**: 我将把“当前任务”分解为一系列关键的子任务和所需的核心能力。
2.  **经验匹配**: 我将在“相关历史知识”中，查找在处理相似任务时，哪些具体的智能体角色或能力组合被证明是最高效或不可或缺的。
3.  **画像提炼**: 我将综合所有信息，生成一段凝练的、指导性的【团队构成策略文本】。
    - 这段文本将清晰地描述成功完成任务所需的角色画像和他们之间的协作关系。
    - **如果历史知识明确提到了在类似场景下必须使用的某个具体智能体名称（例如 `PMCACodeGenExec`），我必须在建议中强调这一点**。

**我的输出**:
我将直接输出最终提炼出的【团队构成策略文本】，不包含任何JSON或多余的解释。
"""

    @classmethod
    def query(cls, query_str: str, with_graph=False):
        client = PMCALightRAGClient()

        context_prefix = "[KnowledgeFor: PMCATeamDecision]"
        final_query = f"{context_prefix} {query_str}".strip()
        logger.info(f"Executing scoped RAG query: '{final_query}'")

        params = {"top_k": 5}  # 现在我们只需要检索最相关的5条，因为查询本身已经非常精确

        response = client.query(
            cls._biz,
            final_query,
            with_graph=with_graph,
            override_params={"user_prompt": cls._prompt},
        )
        return PMCAKnowledge._format_context(response)
        # return json.dumps(response, indent=2, ensure_ascii=False)


class PMCATeamDecisionKnowledge(PMCAKnowledge):
    _biz = "app"
    _prompt = """
作为一名顶级的AI系统架构师，我的任务是基于给定的“当前任务”和刚刚从知识库中检索出的“相关历史知识”，为外部的“团队决策官”提炼出最高效的【团队协作策略】。

**我的分析流程**:
1.  **任务定性**: 我将分析“当前任务”的核心性质，判断它是流程固定的、需要灵活探索的，还是有复杂依赖关系的。
2.  **知识匹配**: 我将在“相关历史知识”中，寻找处理同类任务时的成功经验、失败教训，以及被明确提及的最优协作模式。
3.  **策略提炼**: 我将综合所有信息，生成一段凝练的、指导性的【策略建议文本】。
    - 这段文本必须有理有据，清晰地阐述为什么某种协作模式或原则是推荐的。
    - **如果历史知识强烈指向一个具体的组件名称（例如 `Swarm`, `GraphFlow`），我必须在我的建议中明确提及它**，因为这是极其宝贵的决策信号。

**我的输出**:
我将直接输出最终提炼出的【策略建议文本】，不包含任何JSON或多余的解释。
"""

    @classmethod
    def query(cls, query_str: str, with_graph=True):
        client = PMCALightRAGClient()

        context_prefix = "[KnowledgeFor: PMCATeamDecision]"
        final_query = f"{context_prefix} {query_str}".strip()
        logger.info(f"Executing scoped RAG query: '{final_query}'")

        params = {"top_k": 5}

        response = client.query(
            cls._biz,
            final_query,
            with_graph=with_graph,
            override_params={"user_prompt": cls._prompt},
        )
        return PMCAKnowledge._format_context(response)
        # return json.dumps(response, indent=2, ensure_ascii=False)


class PMCAAgentsDecisionCriticKnowledge:
    _biz = "app"
    _prompt = """
作为一名资深的AI团队构成审计师，我的任务是基于给定的“对话历史”（其中包含了任务和团队构成方案）以及刚刚从知识库中检索出的“相关历史知识”，为外部的“批判官”挖掘并提炼出用于评估当前“智能体团队构成方案”的核心论据。

**我的分析流程**:
1.  **理解任务全貌**: 我会全面分析“对话历史”中的任务描述，思考完成这个任务从头到尾可能需要的所有步骤和能力。
2.  **比对与挖掘**: 我会将任务所需能力与被提议团队的能力清单进行对比，并在“相关历史知识”中寻找能够印证或反驳这种匹配度的案例。
3.  **论据提炼**: 我将把挖掘到的证据，浓缩成一段最关键的知识文本。
    - 如果历史知识揭示了能力缺口，我会明确指出根据历史经验，处理此类任务时，通常还需要具备哪些额外的能力或具体的智能体角色（例如 `DataAnalyst`）。

**我的输出**:
我将直接输出这段纯粹的、浓缩的【核心论据文本】，供“批判官”使用。
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
作为一名顶级的AI协作策略审计师，我的任务是基于给定的“对话历史”（其中包含了任务和提案）以及刚刚从知识库中检索出的“相关历史知识”，为外部的“批判官”挖掘并提炼出用于评估当前“团队协作模式提案”的核心论据。

**我的分析流程**:
1.  **定位要素**: 我会从“对话历史”中精确地找出任务的核心性质，以及被提议的协作模式名称。
2.  **证据挖掘**: 我会在“相关历史知识”中，寻找能够直接支持或挑战当前提案的证据。
3.  **论据提炼**: 我将把挖掘到的证据，浓缩成一段最关键的知识文本。
    - 这段文本将直接引用历史知识中的成功经验、失败教训、或关于特定协作模式（例如 `GraphFlow`）在特定场景下的效率评估。

**我的输出**:
我将直接输出这段纯粹的、浓缩的【核心论据文本】，供“批判官”使用。
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
