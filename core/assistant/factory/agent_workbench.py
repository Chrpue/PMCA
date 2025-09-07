import asyncio
from typing import List
from loguru import logger
from autogen_ext.tools.mcp import McpWorkbench, SseServerParams
from autogen_core.tools import Workbench as BaseWorkbench


class PMCACombinedWorkbench(BaseWorkbench):
    """Combined MCP Workbench"""

    def __init__(self, server_params_list: List[SseServerParams]):
        # 为每个 ServerParam 创建一个 McpWorkbench 客户端
        self._workbenches = [McpWorkbench(params) for params in server_params_list]

    @property
    def workbenches(self):
        return self._workbenches

    async def start(self):
        """start all workbench sse"""
        await asyncio.gather(*(wb.start() for wb in self._workbenches))

    async def stop(self):
        """stop all workbench sse"""
        await asyncio.gather(*(wb.stop() for wb in self._workbenches))

    async def reset(self):
        pass

    async def save_state(self):
        """save all workbench state"""
        await asyncio.gather(*(wb.save_state() for wb in self._workbenches))

    async def load_state(self):
        pass

    # async def list_tools(self):
    #     """get all aviliable tools"""
    #     all_tools = await asyncio.gather(*(wb.list_tools() for wb in self._workbenches))
    #
    #     # return [tool for sub in all_tools for tool in sub]
    #     return [{**tool, "strict": True} for sub in all_tools for tool in sub]

    async def list_tools(self):
        """get all aviliable tools"""
        all_tools = await asyncio.gather(*(wb.list_tools() for wb in self._workbenches))

        return [tool for sub in all_tools for tool in sub]

    async def call_tool(self, name: str, arguments: dict, **kwargs):
        """choice target tool"""

        logger.error(kwargs)
        for wb in self._workbenches:
            tools = await wb.list_tools()

            if any(tool["name"] == name for tool in tools):
                return await wb.call_tool(name, arguments, **kwargs)
        raise ValueError(f"No tool named '{name}' found in any MCP server.")
