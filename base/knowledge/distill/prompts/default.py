"""
Default prompt template for the distillation subsystem.

This module defines two string constants, ``topic_prompt`` and
``distill_prompt``, which are formatted with ``str.format`` at runtime.
The variables ``{agent_name}``, ``{topics}`` and ``{rag_answer}`` will be
substituted by the pipeline.
"""

topic_prompt: str = (
    "基于你拥有的全部知识，请列出与 '{agent_name}' 智能体的核心职责、决策策略和工作流最相关的核心主题关键词。"
    "请只返回关键词列表，用逗号分隔。"
)

distill_prompt: str = (
    "你是一位顶级的认知架构师。你的任务是为名为 '{agent_name}' 的AI智能体，根据下方由LightRAG提供的深度知识，生成一个结构化的JSON记忆档案。"
    "这个JSON档案必须包含以下四个键：'persona', 'core_memory_principles', 'episodic_memories', 'procedural_memories'。\n\n"
    "1.  `persona`: 提炼一句（不超过50字）关于该智能体核心身份、使命和性格的第一人称描述。\n"
    "2.  `core_memory_principles`: 提炼出3-5条该智能体必须遵守的、永恒不变的核心原则或真理。这是一个字符串列表。\n"
    "3.  `episodic_memories`: 将知识中的具体案例或场景，转化为1-3条“我记得一个经验/案例...”形式的第一人称情景记忆。这是一个字符串列表。\n"
    "4.  `procedural_memories`: 将知识中的工作流程，提炼成1-2条“当处理...任务时，我的标准流程是：...”形式的第一人称程序性记忆。这是一个字符串列表。\n\n"
    "如果某个类型的记忆在提供的知识中不适用或无法提炼，请返回一个空列表 `[]`。"
    "请严格按照JSON格式输出，不要包含任何额外的解释或Markdown标记。\n\n"
    "[LightRAG 提供的深度知识]\n{rag_answer}"
)
