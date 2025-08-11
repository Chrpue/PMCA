from base.agents.factory import PMCAAgentFactory, PMCAAgentMetadata


@PMCAAgentFactory.register("PMCAGraphFinished")
class PMCAGraphFinished(PMCAAgentMetadata):
    description = "GraphFlow终结智能体."
    system_message = """
你是GraphFlow执行控制智能体，当流程节点走到你这的时候标志着任务已经执行完毕，你要做的唯一的事情是返回 `已完成您的指示工作 [GRAPH FINISHED]` .
"""
    required_mcp_keys = []

    chinese_name = "任务终结助手"

    duty = """
    一个占位智能体，不做任何事.
"""
