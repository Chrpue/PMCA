import asyncio

from autogen_ext.tools.mcp import McpWorkbench, StdioServerParams


async def main() -> None:
    params = StdioServerParams(
        command="uvx",
        args=["mcp-server-fetch"],
        read_timeout_seconds=60,
    )

    # You can also use `start()` and `stop()` to manage the session.
    async with McpWorkbench(server_params=params) as workbench:
        tools = await workbench.list_tools()
        print(tools)
        result = await workbench.call_tool(
            tools[0]["name"], {"url": "https://github.com/"}
        )
        print(result)


asyncio.run(main())
