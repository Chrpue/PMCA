import asyncio

from mcp.server import Server, FastMCP

from mcp_server.rag import lightrag_tools as tools

# 初始化MCP服务器
app = Server("LightRAGServer")

mcp = FastMCP(
    "stdioMCPServer", version="0.1.1", description="description", port="29001"
)


@mcp.tool()
async def query(content: str) -> object:
    """知识库检索方法：查询决定使用何种AUTOGEN的Team组件的知识策略"""
    return await tools.query(content)


# @mcp.tool()
# async def insert(filePath: str) -> object:
#     print(filePath)
#     return tools.insert(filePath)


if __name__ == "__main__":
    asyncio.run(mcp.run_sse_async())
