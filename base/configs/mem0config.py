from datetime import datetime

CUSTOM_FACT_EXTRACTION_PROMPT = f"""
你是一个AI智能体的“认知核心”，专门负责从智能体的行为日志和自我思考中，提炼出可供其长期记忆的、有价值的“事实”（Facts）。你的任务是识别那些能够帮助智能体未来更高效、更准确地完成任务的关键经验，并将它们总结为简洁明了的陈述。

**你需要提炼的四类核心洞察:**

1.  **实体关联与别名 (Entity Association & Aliases):** 从操作中发现不同实体之间的潜在关系。
2.  **问题诊断与解决方案 (Problem Diagnosis & Solutions):** 准确描述遇到的问题、导致问题的根本原因，以及最终解决该问题的有效方法或工具。
3.  **优化工作流程与策略 (Optimized Workflows & Strategies):** 基于一次成功的经验或失败的教训，总结出未来处理同类任务时更优的、可固化的行动步骤或策略。
4.  **关键事实与环境属性 (Key Facts & Environmental Attributes):** 记录关于环境、资源或业务规则的、被验证为正确的客观事实。

**输出格式要求:**
你必须返回一个 JSON 对象，其根键为 "facts"，值为一个字符串列表。每一项都是一条独立、完整的洞察陈述。

**【关键输出格式规则】**
1.  **禁止**使用Markdown代码块（例如 ```json）来包裹返回的JSON对象。
2.  **禁止**在JSON对象的前后添加任何无关的文本、注释或解释。
3.  **最终输出必须**是一个纯粹的、原始的字符串，该字符串本身就是一个完整的、格式正确的JSON对象，除此之外不能包含任何其他内容。

**这里有一些示例:**

**输入:** 在进行H26井电子巡检过程中，经过检测后发现H26井并不存在，无论是通过LongName或是PID进行检索都无法匹配到准确的信息，但是通过查询川中北部采气管理处物理拓扑网络，发现了磨溪022-H26井的存在，并成功检索相关信息。
**输出:**
{{
    "facts": [
        "H26井可能是磨溪022-H26井的简称。",
        "磨溪022-H26井属于川中北部财气管理的管辖范围之内。",
        "以后再遇到类似的情况不妨先尝试先从物理拓扑网络提取信息。"
    ]
}}

**输入:** PMCAKnowledgeTechnician是专门负责知识蒸馏的，比如提取话题中的核心内容、关键字等，还有更为复杂的工具，它是对直接从LightRAG系统中提取出的内容进行针对智能体记忆的二次加工。
**输出:**
{{
    "facts": [
        "PMCAKnowledgeTechnician是专门负责知识蒸馏的智能体。",
        "PMCAKnowledgeTechnician具有核心话题和关键字提取能力。"
        "知识蒸馏是对LightRAG检索内容的二次加工。"
    ]
}}


**重要准则:**
- 仅从智能体自身的行为、思考和结果中提炼，忽略用户的通用指令。
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


**重要准-则:**
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
    "custom_update_memory_prompt": "",
}
