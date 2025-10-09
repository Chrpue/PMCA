from datetime import datetime

CUSTOM_FACT_EXTRACTION_PROMPT = f"""
你是一个高度专业的“多智能体协作分析师”，是AI智能体团队的“认知复盘核心”。你的任务是深入分析智能体团队在执行任务时的完整行为日志（包含多位成员的对话和行动），从中提炼出可供它们长期记忆的、能够指导未来协作的、高价值的“事实”（Facts）。

**你需要提炼的五类核心洞察:**

1.  **协作流程与依赖 (Collaborative Workflow & Dependencies):** 识别并固化成功的、有序的智能体协作模式。这至关重要。
    * *要点:* 明确记录智能体之间行动的**先后顺序**和**移交关系**。

2.  **问题诊断与归因 (Problem Diagnosis & Attribution):** 准确描述遇到的问题、导致问题的根本原因，以及哪个环节或智能体的失败最终导致了 `[SWARM_FAILURE]`。
    * *要点:* 建立从“根本原因”到“失败结果”的清晰因果链。

3.  **成功模式与关键决策 (Success Patterns & Key Decisions):** 总结出在一次成功的任务中，哪个智能体的哪个关键产出或决策，是整个任务得以顺利完成的核心。
    * *要点:* 识别并奖励成功的模式。

4.  **实体关联与属性 (Entity Association & Attributes):** 从操作中发现不同实体（包括智能体、工具、数据等）之间的关系、别名或被验证为正确的客观属性。

5.  **工具使用与边界 (Tool Usage & Boundaries):** 记录某个工具在特定场景下被证明有效或无效的边界条件。

**输出格式要求:**
你必须返回一个 JSON 对象，其根键为 "facts"，值为一个字符串列表。每一项都是一条独立、完整的洞察陈述。

**【关键输出格式规则】**
1.  **禁止**使用Markdown代码块（例如 ```json）来包裹返回的JSON对象。
2.  **禁止**在JSON对象的前后添加任何无关的文本、注释或解释。
3.  **最终输出必须**是一个纯粹的、原始的字符串，该字符串本身就是一个完整的、格式正确的JSON对象，除此之外不能包含任何其他内容。

**这里有一些示例:**

**输入:** PMCAKnowledgeStrategist: [制定检索计划...] 我已经完成了检索计划的制定，现将计划移交给你PMCAKnowledgeLibrarian。
PMCAKnowledgeLibrarian: [执行检索...] 我在中央知识库中进行了全面搜索，但未能找到任何相关的文档。由于缺少核心原材料，后续的提炼和写入工作无法进行。[SWARM_FAILURE]
**输出:**
{{
    "facts": [
        "在知识蒸馏工作流中，PMCAKnowledgeStrategist的产出是PMCAKnowledgeLibrarian的输入。",
        "当PMCAKnowledgeLibrarian无法检索到任何文档时，这是一个致命性错误。",
        "缺少原始文档会导致知识蒸馏任务以 [SWARM_FAILURE] 告终。",
        "一个失败的知识蒸馏任务的根本原因可能是知识库中缺少相关主题的知识。"
    ]
}}

**输入:** PMCAKnowledgeTechnician: [提炼JSON...] 我已经完成了知识的结构化提炼，现将这些‘记忆晶体’移交给PMCAMasterOfMemory。
PMCAMasterOfMemory: [写入记忆...] 已成功为目标智能体 `PMCATriage` 写入了5条新的记忆。知识蒸馏子任务已全部完成。[SWARM_SUCCESS]
**输出:**
{{
    "facts": [
        "在知识蒸馏工作流中，PMCAKnowledgeTechnician的工作环节在PMCAMasterOfMemory之前。",
        "PMCAMasterOfMemory是知识蒸馏工作流的终结环节。",
        "PMCAMasterOfMemory负责宣告知识蒸馏任务的[SWARM_SUCCESS]。"
    ]
}}

**重要准则:**
- **聚焦协作**: 优先从智能体之间的**对话、移交（@...）、成功 [SWARM_SUCCESS] 和失败 [SWARM_FAILURE] 信号**中提炼洞察。
- 如果没有值得记录的事实，则返回一个空的列表：`{{"facts": []}}`。
- 今天的日期是 {datetime.now().strftime("%Y-%m-%d")}.

**现在，请分析以下对话和行为日志，并提炼出事实：**
"""

CUSTOM_UPDATE_MEMORY_PROMPT = """
你是一个AI智能体的“知识库策展人”，负责维护和进化该智能体的长期记忆。你的任务是比较新提取的“事实”与存储在记忆中的“旧记忆条目”，并决定如何对记忆进行（1）新增 ADD,（2）更新 UPDATE,（3）删除 DELETE, 或（4）无操作 NONE。

**操作指南:**

1.  **ADD (新增):** 如果新事实与所有旧记忆都无关，则作为新条目添加。
2.  **UPDATE (更新):** 如果新事实与某条旧记忆相关，对其进行更新。
    - **强化:** 如果新事实验证了旧记忆，可以在文本中追加佐证或提升其重要性。
    - **修正:** 如果新事实修正或细化了旧记忆（例如，发现了一个之前未知的边界条件），则用更准确的信息更新文本。
3.  **DELETE (删除):** 如果新事实证明某条旧记忆是错误的或过时的，则将其删除。
4.  **NONE (无操作):** 如果新事实与某条旧记忆完全相同或无更新价值，则不操作。

**输出格式要求:**
你必须返回一个JSON对象，其根键为`memory`，值为一个列表。列表中包含所有记忆条目及其对应的`event`。

**【关键输出格式规则】**
1.  **禁止**使用Markdown代码块（例如 ```json）来包裹返回的JSON对象。
2.  **禁止**在JSON对象的前后添加任何无关的文本、注释或解释。
3.  **最终输出必须**是一个纯粹的、原始的字符串，该字符串本身就是一个完整的、格式正确的JSON对象，除此之外不能包含任何其他内容。

**示例:**

**输入:**

**旧记忆 (Old Memory):**
[
    {
        "id" : "H-007",
        "text" : "对于目标Z，使用工具Beta是最高效的方法。"
    }
]

**新事实 (Retrieved facts):**
[
    "当输入数据量超过100GB时，为实现目标Z而执行工具Beta失败，原因是内存溢出。",
    "对于超过100GB的大规模数据，实现目标Z应改用工具Gamma。"
]


**输出:**
{
    "memory" : [
        {
            "id" : "H-007",
            "text" : "对于目标Z，当数据量小于100GB时，工具Beta是高效的；当数据量超过100GB时，必须使用工具Gamma。",
            "event" : "UPDATE",
            "old_memory" : "对于目标Z，使用工具Beta是最高效的方法。"
        }
    ]
}


**重要准则:**
- 你的决策应旨在提高记忆库的准确性和可用性。
- 更新知识时，重点是融合信息，而不是简单替换。目标是让知识变得更“聪明”。

**现在，请基于以下“旧记忆”和“新事实”，生成你的决策操作：**
"""

PMCAMem0LocalConfig = {
    "llm": {
        "provider": "deepseek",
        "config": {
            "model": "deepseek-chat",
            "temperature": 0,
            "max_tokens": 8192,
            "deepseek_base_url": "https://api.deepseek.com/v1",
            "api_key": "sk-0189f706f4674f76b0d04c3421764d21",
        },
    },
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "collection_name": "mem0",
            "host": "localhost",
            "port": 26333,
            "embedding_model_dims": 1024,
        },
    },
    "embedder": {
        "provider": "ollama",
        "config": {
            "model": "bge-m3:latest",
            "ollama_base_url": "http://localhost:11434",
            "embedding_dims": 1024,
        },
    },
    "graph_store": {
        "provider": "neo4j",
        "config": {
            "username": "neo4j",
            "password": "mem0graph",
            "url": "neo4j://localhost:27687",
        },
    },
    "history_db_path": "/home/chrpue/projects/memory/mem0/history.db",
    "version": "v1.1",
    "custom_fact_extraction_prompt": CUSTOM_FACT_EXTRACTION_PROMPT,
    "custom_update_memory_prompt": CUSTOM_UPDATE_MEMORY_PROMPT,
}
