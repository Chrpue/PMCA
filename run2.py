from autogen_core.tools import ToolResult, Workbench
from autogen_ext.tools.mcp import McpWorkbench, SseServerParams


import asyncio
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import TextMentionTermination, TextMessageTermination
from autogen_agentchat.ui import Console
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_ext.tools.mcp import McpWorkbench, StdioServerParams, SseServerParams

from client.llm_client import LLMClient


from autogen_core.tools import Workbench as BaseWorkbench


class CombinedWorkbench(BaseWorkbench):
    def __init__(self, server_params_list: list[SseServerParams]):
        # 为每个 ServerParam 创建一个 McpWorkbench 客户端
        self._workbenches = [McpWorkbench(params) for params in server_params_list]

    async def start(self):
        # 并行启动所有 Workbench SSE 连接
        await asyncio.gather(*(wb.start() for wb in self._workbenches))

    async def stop(self):
        # 停止所有连接
        await asyncio.gather(*(wb.stop() for wb in self._workbenches))

    async def reset(self):
        pass

    async def save_state(self):
        await asyncio.gather(*(wb.save_state() for wb in self._workbenches))

    async def load_state(self):
        pass

    async def list_tools(self):
        # 合并底层所有工具列表
        all_tools = await asyncio.gather(*(wb.list_tools() for wb in self._workbenches))
        # 返回一个扁平化列表
        return [tool for sub in all_tools for tool in sub]

    async def call_tool(self, name: str, arguments: dict, **kwargs):
        # 查找哪个 Workbench 注册了该工具
        for wb in self._workbenches:
            tools = await wb.list_tools()
            if any(tool["name"] == name for tool in tools):
                return await wb.call_tool(name, arguments, **kwargs)
        raise ValueError(f"No tool named '{name}' found in any MCP server.")


async def main() -> None:
    model_client = LLMClient.get_llm_client("qwen", "base")

    excel_server_params = SseServerParams(url="http://127.0.0.1:11001/sse", timeout=20)
    quickchart_server_params = SseServerParams(
        url="http://127.0.0.1:11002/sse", timeout=20
    )
    combined_wb = CombinedWorkbench([excel_server_params, quickchart_server_params])

    async with combined_wb:
        agent = AssistantAgent(
            "web_browsing_assistant",
            model_client=model_client,
            workbench=combined_wb,
            model_client_stream=True,
            system_message="你是一个负责处理数据的助手，你可以处理excel和quickchart的相关工作，善用你的工具完成任务，若有图像生成应将图像下载至本地（路径为/home/chrpue/projects/PMCA/files）结束返回TERMINATE",
        )
        team = RoundRobinGroupChat([agent], TextMentionTermination("TERMINATE"))
        await Console(
            team.run_stream(
                task="随机生成100个数值为30~50的浮点型数据，保留两位小数，并以曲线图显示"
            )
        )


asyncio.run(main())
