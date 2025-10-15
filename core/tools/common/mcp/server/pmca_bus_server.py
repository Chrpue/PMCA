#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Dict, Any, Literal, Optional, List
import asyncio

from fastmcp import FastMCP

_subscribers: List[asyncio.Queue] = []
mcp = FastMCP("pmca-control-bus")


@mcp.tool
async def report_status(
    caller: str,
    task_id: str,
    status: Literal[
        "[ASSISTANT:OK]",
        "[ASSISTANT:RETRY]",
        "[ASSISTANT:NEEDUSER]",
        "[ASSISTANT:IRRECOVERABLE]",
    ],
    detail: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    evt = {
        "type": "TaskStatus",
        "caller": caller,
        "task_id": task_id,
        "status": status,
        "detail": detail or {},
    }
    for q in list(_subscribers):
        await q.put(evt)
    return {"ok": True, "event": evt}


@mcp.tool
async def report_final(
    caller: str,
    task_id: str,
    reason: Literal["[EXECUTE_SUCCESS]", "[EXECUTE_FAILURE]", "[EXECUTE_CANCEL]"],
    summary: Optional[str] = None,
) -> Dict[str, Any]:
    evt = {
        "type": "TaskFinal",
        "caller": caller,
        "task_id": task_id,
        "reason": reason,
        "summary": summary or "",
        "termination": True,
    }
    for q in list(_subscribers):
        await q.put(evt)
    return {"ok": True, "event": evt}


app = mcp.http_app()
