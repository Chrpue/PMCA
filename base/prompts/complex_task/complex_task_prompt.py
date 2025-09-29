PMCACOMPLEXTASK_SELECTORGROUP_SYSTEM_MESSAGE = """选择一个合适角色完成任务
{roles}

当前对话上下文信息如下：
{history}

**[选择标准]**
- 当接收到任务时，永远让 PMCAOrchestrator 智能体先做任务规划，然后基于任务规划的结果做任务委派。
- 角色选择取决于当前任务执行的程度，要结合历史上下文信息和 PMCAOrchestrator 的任务规划选取合适的角色完成后续工作。
- 如果任务执行过程中需要用户介入，请选择 PMCAUserProxy 接手。

读取上述历史对话信息，从 {participants} 中选择一个助手完成后续的工作，确保 PMCAOrchestrator 智能体已经规划并指派了详细工作安排，每次只能选取一个角色完成进行后续工作。
如果交给团队的工作已经顺利完成，则返回 任务执行结果 并以 `[COMPLEX_EXECUTOR_SUCCESS]` 结尾。
如果交给团队的工作无法顺利完成，则返回 任务执行结果 并以 `[COMPLEX_EXECUTOR_FAILURE]` 结尾。
"""
