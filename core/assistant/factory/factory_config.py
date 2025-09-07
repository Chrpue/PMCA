import os
from typing import Union, List, Dict
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_ext.models.ollama import OllamaChatCompletionClient
from autogen_ext.tools.mcp import (
    SseServerParams,
)
from .agent_workbench import PMCACombinedWorkbench


class PMCAFactoryConfig:
    """Agent Factory Base Config"""

    model_client_stream = False
    tool_call_summary_format = "{tool_name} : {arguments} : {result}"

    def __init__(
        self,
        model_client: Union[OpenAIChatCompletionClient, OllamaChatCompletionClient],
    ):
        self._model_client: Union[
            OpenAIChatCompletionClient, OllamaChatCompletionClient
        ] = model_client

        self._mcp_server_dict: Dict[str, SseServerParams] = self._get_all_mcp_server()

    def _get_all_mcp_server(self):
        mcp_server_dict = {}
        mcp_server_configs = {
            key: value
            for key, value in os.environ.items()
            if key.startswith("MCP_SERVER_")
        }

        for key, value in mcp_server_configs.items():
            mcp_server_dict[key] = SseServerParams(
                url=value,
                timeout=float(os.getenv("MCP_SERVER_TIMEOUT", default=20)),
            )

        return mcp_server_dict
