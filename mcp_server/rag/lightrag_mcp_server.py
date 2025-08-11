import uvicorn
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool
from starlette.applications import Starlette
from starlette.routing import Route, Mount

from loguru import logger

from mcp_server.rag import lightrag_tools as tools


# 初始化MCP服务器
app = Server("LightRAG-mcp-server")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """列出可用的工具
    返回:
        list[Tool]: 工具列表，每个工具包含名称、描述和参数信息
    """
    return [
        Tool(
            name="query,",
            description="根据用户任务描述，在知识库中检索应选用什么AUTOGEN的Team组件的相关知识，检索模式为全局检索（global）",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {"type": "str", "description": "用户任务描述"},
                },
                "required": ["contont"],
            },
        ),
        Tool(
            name="insert",
            description="在知识库中构建知识的工具",
            inputSchema={
                "type": "object",
                "properties": {
                    "area": {"type": "str", "description": "插入的知识库名称"},
                    "file_path": {
                        "type": "str",
                        "description": "插入知识的文本路径，文本为.txt格式",
                    },
                    "ids": {"type": "str", "description": "构建知识的索引id"},
                },
                "required": ["area", "file_path", "ids"],
            },
        ),
    ]


@app.call_tool()
async def query(content: str) -> object:
    print(content)
    return tools.ir_retrivier_global(content)


sse = SseServerTransport("/messages/")


async def handle_sse(request):
    async with sse.connect_sse(
        request.scope, request.receive, request._send
    ) as streams:
        await app.run(streams[0], streams[1], app.create_initialization_options())


# Create Starlette app with routes
starlette_app = Starlette(
    debug=True,
    routes=[
        Route("/sse", endpoint=handle_sse),
        Mount("/messages/", app=sse.handle_post_message),
    ],
)

if __name__ == "__main__":
    uvicorn.run(starlette_app, host="0.0.0.0", port=29001)
