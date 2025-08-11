import asyncio
from typing import Optional, Any
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()  # load environment variables from .env


class MCPClient:
    def __init__(self):
        # Initialize session and client objects
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.anthropic = Anthropic()

    # 连接服务
    async def connect_to_server(self,command:str,args:str) -> object:
        """Connect to an MCP server

        Args:
            server_script_path: Path to the server script (.py or .js)
        """
        # is_python = server_script_path.endswith('.py')
        # is_js = server_script_path.endswith('.js')
        # if not (is_python or is_js):
        #     raise ValueError("Server script must be a .py or .js file")

        # command = "python" if is_python else "node"
        server_params = StdioServerParameters(
            command=command,
            args=[args],
            env=None
        )

        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))

        await self.session.initialize()

        # List available tools
        response = await self.session.list_tools()
        tools = response.tools
        print("\nConnected to server with tools:", [tool.name for tool in tools])
        return tools

    # 调用工具
    async def call_tool(self, tool_name: str, tool_args: dict[str, Any] | None) -> object:
        return await self.session.call_tool(tool_name, tool_args)

    async def cleanup(self):
        """Clean up resources"""
        await self.exit_stack.aclose()


async def main():
    client = MCPClient()
    try:
        await client.connect_to_server()
        # await client.call_tool() 调用工具方法
    finally:
        await client.cleanup()


if __name__ == "__main__":

    asyncio.run(main())
