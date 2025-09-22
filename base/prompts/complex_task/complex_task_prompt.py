PMCACOMPLEXTASK_SELECTORGROUP_SYSTEM_MESSAGE = """
{roles}

当前对话上下文信息如下：
{history}

读取上述历史对话信息，从 {participants} 中选择一个助手完成后续的工作，确保 PMCAOrchestrator 智能体已经规划并指派了详细工作安排，每次只能选取一个助手完成。
如果交给团队的工作已经顺利完成，则返回 任务执行结果 并以 `[SWARM_SUCCESS]` 结尾。
如果交给团队的工作无法顺利完成，则返回 任务执行结果 并以 `[SWARM_FAILURE]` 结尾。
"""
