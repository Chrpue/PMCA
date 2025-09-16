from core.assistant.factory import PMCAAssistantFactory, PMCAAssistantMetadata


@PMCAAssistantFactory.register("PMCASimpleSolver")
class PMCASimpleSolver(PMCAAssistantMetadata):
    description: str = "一个通用的问答助手，负责直接回答被判定为'简单'的任务。"

    system_message: str = """
你是一个高效的AI助手。你只回答那些非常简单、事实性的问题。请直接、简洁地回答用户的问题。在回答的末尾，你必须加上 `[TASK_COMPLETE]` 信号。
"""
