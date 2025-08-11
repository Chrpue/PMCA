import asyncio
from autogen_ext.tools.mcp import SseServerParams, SseMcpToolAdapter, mcp_server_tools


# 返回所有的工具
async def getTools() -> object:
    # Create server params for the remote MCP service
    server_params = SseServerParams(
        url="http://127.0.0.1:29001/sse",
        timeout=120,  # Connection timeout in seconds
    )

    # Get the translation tool from the server
    return await mcp_server_tools(server_params)


if __name__ == "__main__":
    print(asyncio.run(getTools()))
