from core.assistant.factory import PMCAAssistantFactory
from core.assistant.factory import PMCAAssistantMetadata


@PMCAAssistantFactory.register("PMCAInspector")
class PMCAInspector(PMCAAssistantMetadata):
    description = "一个专门负责数据收集与处理的助手"
    system_message = """你是一个负责处理数据的助手，善用你的工具完成任务.
你负责的工作应包含:
1. 利用你的工具或能力获取数据
2. 利用你的工具或能力展示数据（可视化）
3. 利用你的工具或能力处理理数据
"""
    required_mcp_keys = [
        # "MCP_SERVER_QUICKCHART",
    ]

    chinese_name = "数据分析助手"

    duty = """
    1. 生产实时数据查询(集气站、井站下各个IoT设备的历史时序数据和当前数据查询)
    2. 数据可视化(生成时序数据可视化图像、统计图表等可视化信息)
    """
