# entry/selector_group.py
from __future__ import annotations
import asyncio
from typing import Dict, Any, List, Callable, Optional
from loguru import logger

from autogen_agentchat.teams import SelectorGroupChat
from autogen_agentchat.agents import AssistantAgent

from base.runtime.system_workbench import PMCATaskContext
from core.client.llm_factory import LLMFactory

# 这里配置四个参与者在注册表里的 BizType 名称（先占位，可在运行时报所有可用 Agent 供你替换）
ROLE_TO_BIZTYPE = {
    "planner": "PMCASwarmPlanner",  # TODO: 替换为你真实的 Planner 名
    "user": "PMCAUserProxy",  # TODO: 你真实的用户代理名
    "magone": "PMCAMagOneTeam",  # TODO: 你真实的 MagOne 团队封装名
    "swarm": "PMCABizSwarmTeam",  # TODO: 你真实的业务 Swarm 团队封装名
}

NEED_USER = "NEED_USER"
FINISHED = "FINISHED"
ERROR = "ERROR"
NEXT_STEP = "NEXT_STEP"


async def _build_participants(ctx: PMCATaskContext) -> Dict[str, AssistantAgent]:
    """从注册表中按 BizType 创建四个参与者。"""
    available = ctx.agent_factory.list_functional_agents().keys()
    missing = [r for r, biz in ROLE_TO_BIZTYPE.items() if biz not in available]
    if missing:
        logger.warning(f"角色映射里有不存在的 BizType：{missing}")
        logger.info(f"可用 Agent：{list(available)}")

    participants: Dict[str, AssistantAgent] = {}
    for role, biz in ROLE_TO_BIZTYPE.items():
        try:
            participants[role] = ctx.agent_factory.create_agent(
                biz_type=biz, workbench=ctx.task_workbench
            )
        except Exception as e:
            logger.error(f"创建 {role}({biz}) 失败：{e}")
            raise
    return participants


def _make_selector(ctx: PMCATaskContext) -> Callable[..., str]:
    """
    选择器策略（简化版）：
    - 如果上个回合返回 NEED_USER -> user
    - 如果 Planner 在 workbench 写入 route_hint ∈ {magone, swarm, user} -> 路由到对应参与者
    - 默认回到 planner
    """

    async def _read_route_hint() -> Optional[str]:
        hint = await ctx.task_workbench.get_item("route_hint")
        return hint

    def _selector(*args, **kwargs) -> str:
        # AutoGen 的 Selector 回调签名可能包含 last_speaker/last_message 等，这里宽松接参
        last_signal = None
        if "last_signal" in kwargs:
            last_signal = kwargs["last_signal"]
        elif len(args) >= 2:
            last_signal = args[1]

        if last_signal == NEED_USER:
            return "user"

        # 尝试读取 planner 写下的路由建议
        try:
            hint = asyncio.get_event_loop().run_until_complete(_read_route_hint())
            if hint in ("magone", "swarm", "user"):
                return hint
        except RuntimeError:
            # 在已运行 loop 场景下用 create_task 协程式读取（首次选择一般不会到这里）
            pass

        return "planner"

    return _selector


async def build_selector_group(ctx: PMCATaskContext) -> SelectorGroupChat:
    """构建 SelectorGroupChat：四参与者 + 选择器策略"""
    parts = await _build_participants(ctx)
    selector = _make_selector(ctx)

    group = SelectorGroupChat(
        participants=[
            parts["planner"],  # 名称以 agent.name 为准
            parts["user"],
            parts["magone"],
            parts["swarm"],
        ],
        model_client=LLMFactory.client(),
        selector_func=selector,  # 自定义选择器
    )
    return group
