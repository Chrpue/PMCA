#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Dict, Any, Literal, Optional, List
import asyncio
import uuid

from fastmcp import FastMCP

# 订阅者（例如 orchestrator / 前端桥接层）
_subscribers: List[asyncio.Queue] = []

mcp = FastMCP("pmca-control-bus")


@mcp.tool
async def subscribe() -> Dict[str, Any]:
    """
    订阅总线事件（长轮询/流式消费场景可用）。
    返回一个一次性“收件箱”标识；调用方需在宿主侧维护 queue 的消费。
    实际生产中请改造成 SSE/WebSocket；此方法仅保留占位。
    """
    q: asyncio.Queue = asyncio.Queue()
    _subscribers.append(q)
    return {"ok": True, "inbox_size": len(_subscribers)}


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
    """
    上报任务**阶段性执行状态**（不中止）。由“执行智能体”调用。

    参数
    ----
    caller : str
        上报者（执行智能体名），例如 "PMCAKnowledgeLibrarian"。
    task_id : str
        全局任务 ID（由 PMCAOrchestrator 分配并传递）。
    status : Literal[[ASSISTANT:OK] | [ASSISTANT:RETRY] | [ASSISTANT:NEEDUSER] | [ASSISTANT:IRRECOVERABLE]]
        阶段性状态信号。
        - [ASSISTANT:OK]            ：阶段工作正常推进
        - [ASSISTANT:RETRY]         ：尝试重试（通常伴随内部自我修正）
        - [ASSISTANT:NEEDUSER]      ：需要用户澄清/补充
        - [ASSISTANT:IRRECOVERABLE] ：当前任务不可恢复（建议 PMCAOrchestrator 再规划/降级）
    detail : dict | None
        详情(可选)。仅允许少量键：{"summary": str, "step_hint": str}
        - summary  ：1–2 句“做了什么/接下来要做什么/卡在哪里”的短句
        - step_hint：可选定位提示（如 "S1" 或 "retrieve"），便于 PMCAOrchestrator 对照对应子目标

    返回（JSON-RPC result）
    ----------------------
    {
      "ok": true,
      "event": {
        "status": "[ASSISTANT:OK|ASSISTANT:RETRY|ASSISTANT:NEEDUSER|ASSISTANT:IRRECOVERABLE]",
        "task_id": "<task_id>",
        "caller": "<caller>",
        "summary": "<短句>",
        "event_id": "<uuid4>",
        "step_hint": "<可选>"
      }
    }

    使用示例
    ---------------------
    调用本工具时，请只提供**短句**摘要，不要粘贴长历史或大段日志。例如：
    report_status(
      caller="PMCAKnowledgeLibrarian",
      task_id="${TASK_ID}",
      status="[ASSISTANT:OK]",
      detail={"summary": "已收集候选资料，准备筛选", "step_hint": "S1"}
    )

    说明
    ----
    - 本调用**不会**终止团队；SelectorGroupChat 的终止只由硬信号触发。
    - 统一、极简的字段有利于 orchestrator 精准跟踪与再规划，避免上下文爆炸。
    """
    summary = (detail or {}).get("summary") if isinstance(detail, dict) else None
    step_hint = (detail or {}).get("step_hint") if isinstance(detail, dict) else None

    event = {
        "status": status,
        "task_id": task_id,
        "caller": caller,
        "summary": summary or "",
        "event_id": str(uuid.uuid4()),
    }
    if step_hint:
        event["step_hint"] = str(step_hint)

    for q in list(_subscribers):
        await q.put(event)

    return {"ok": True, "event": event}


@mcp.tool
async def report_final(
    caller: str,
    task_id: str,
    reason: Literal["[EXECUTE_SUCCESS]", "[EXECUTE_FAILURE]", "[EXECUTE_CANCEL]"],
    summary: Optional[str] = None,
    step_hint: Optional[str] = None,
) -> Dict[str, Any]:
    """
    上报**当前子任务的最终结果**（候选终止）。由“执行智能体”调用。
    PMCAOrchestrator 收到后将根据 summary 决定是否推进下一步或收束整项任务。

    参数
    ----
    caller : str
        上报者（执行智能体名），例如 "PMCAKnowledgeTechnician"。
    task_id : str
        全局任务 ID。
    reason : Literal[[EXECUTE_SUCCESS] | [EXECUTE_FAILURE] | [EXECUTE_CANCEL]]
        终局结果。
        - [EXECUTE_SUCCESS] ：本子目标达成
        - [EXECUTE_FAILURE] ：本子目标失败
        - [EXECUTE_CANCEL]  ：本子目标取消/中断
    summary : str | None
        1–2 句结果要点（如“写入 120 条记忆片段”/“证据不足，建议缩小范围”）。禁止长历史。
    step_hint : str | None
        可选定位提示，用于 PMCAOrchestrator 将此次结果贴回对应子目标（如 "S3"）。

    返回（JSON-RPC result）
    ----------------------
    {
      "ok": true,
      "event": {
        "reason": "[EXECUTE_SUCCESS|EXECUTE_FAILURE|EXECUTE_CANCEL]",
        "task_id": "<task_id>",
        "caller": "<caller>",
        "summary": "<短句>",
        "event_id": "<uuid4>",
        "step_hint": "<可选>"
      }
    }

    使用示例
    ---------------------
    report_final(
      caller="PMCAKnowledgeTechnician",
      task_id="${TASK_ID}",
      reason="[EXECUTE_SUCCESS]",
      summary="蒸馏片段已写入记忆库，共 120 条",
      step_hint="S3"
    )

    说明
    ----
    - 该事件是“候选终止”，是否收束由 orchestrator 决定（例如在完成所有必选步后输出 [ORCH_FINAL]）。
    - SelectorGroupChat 的终止器应只匹配**硬信号**（如 [SWARM_FINAL]/[ORCH_FINAL]），避免阶段状态误终止。
    """
    event = {
        "reason": reason,
        "task_id": task_id,
        "caller": caller,
        "summary": summary or "",
        "event_id": str(uuid.uuid4()),
    }
    if step_hint:
        event["step_hint"] = str(step_hint)

    # 广播给订阅者
    for q in list(_subscribers):
        await q.put(event)

    return {"ok": True, "event": event}


app = mcp.http_app()
