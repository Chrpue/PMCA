#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Dict, Any, Literal, Optional, List
import asyncio

from fastmcp import FastMCP

_subscribers: List[asyncio.Queue] = []
mcp = FastMCP("pmca-control-bus")


@mcp.tool
async def pmca_emit_status(
    caller: str,
    task_id: str,
    status: Literal["OK", "RETRY", "NEED_USER", "IRRECOVERABLE"],
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
async def pmca_emit_final(
    caller: str,
    task_id: str,
    reason: Literal["SUCCESS", "FAIL", "CANCEL"],
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


@mcp.tool
async def pmca_subscribe_once(timeout_s: int = 30) -> Dict[str, Any]:
    q: asyncio.Queue = asyncio.Queue(maxsize=1)
    _subscribers.append(q)
    try:
        evt = await asyncio.wait_for(q.get(), timeout=timeout_s)
        return {"ok": True, "event": evt}
    except asyncio.TimeoutError:
        return {"ok": False, "error": "timeout"}
    finally:
        try:
            _subscribers.remove(q)
        except ValueError:
            pass


app = mcp.http_app()
