from __future__ import annotations
from typing import List, Any, Dict
from autogen_ext.tools.mcp import McpWorkbench
from autogen_core.tools import Workbench

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.team.core_assistants.core_assistants import PMCACoreAssistants  # noqa: F401
    from base.runtime.task_context import PMCATaskContext


def _is_core_assistant(name: str) -> bool:
    from core.team.core_assistants.core_assistants import (
        PMCACoreAssistants,
    )  # local import

    return PMCACoreAssistants.is_core_assistant(name)


def build_functional_workbenches(ctx: "PMCATaskContext") -> List[Workbench]:
    """
    读取 .env 中的 FUNCTIONAL_MCP_SERVER（单值）和/或 FUNCTIONAL_SERVER_*（多值），
    统一构造成 McpWorkbench 列表（自动判断SSE|HTTP）。
    """
    server_params_map = ctx.task_env.get_functional_servers()
    return [McpWorkbench(server_params=params) for params in server_params_map.values()]


def merge_functional_workbenches(
    ctx: "PMCATaskContext", assistant_name: str, params: Dict[str, Any]
) -> Dict[str, Any]:
    """
    - 核心智能体：不追加
    - 职能智能体：把 .env 配置的 FUNCTIONAL_MCP_SERVER / FUNCTIONAL_SERVER_* 转换后的
      McpWorkbench（SSE）统一合并进 params["workbench"] 列表。
    """
    if _is_core_assistant(assistant_name):
        return params

    extras: List[Workbench] = build_functional_workbenches(ctx)
    if not extras:
        return params

    if "workbench" in params and params["workbench"]:
        params["workbench"] = [*params["workbench"], *extras]
    else:
        params["workbench"] = extras
    return params
