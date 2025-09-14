# core/team/engine/swarm_engine.py (新建文件)

import asyncio
from typing import Dict, Any, List
from loguru import logger

from autogen_agentchat.teams import Swarm
from autogen_agentchat.messages import BaseChatMessage, TextMessage, HandoffMessage

from base.runtime import PMCATaskContext
from core.team.factory.swarm_factory import PMCASwarmFactory
from core.team.common import PMCARoutingMessages


class PMCASwarmEngine:
    """
    负责Swarm团队生命周期管理的执行引擎。
    它作为一个工具被顶层协调器调用，并处理Swarm的创建、运行、暂停和恢复。
    """

    TEAM_STATE_KEY_PREFIX = "swarm_state_"  # 使用前缀以支持多个Swarm实例

    def __init__(self, ctx: PMCATaskContext):
        self._ctx = ctx
        self._swarm_factory = PMCASwarmFactory(ctx.assistant_factory)

    async def run(
        self,
        team_name: str,
        participant_names: List[str],
        initial_speaker_name: str,
        task: str,
        is_resume: bool = False,
    ) -> str:
        """
        运行或恢复一个Swarm团队。

        Args:
            team_name (str): 团队的唯一标识符。
            participant_names (List[str]): 参与者列表。
            initial_speaker_name (str): 初始发言者。
            task (str): 初始任务描述或用户的后续输入。
            is_resume (bool): 标记本次运行是否为从暂停状态恢复。

        Returns:
            str: 最终的任务结果或一个状态信号（如需要用户输入）。
        """

        state_key = f"{self.TEAM_STATE_KEY_PREFIX}{team_name}"

        # 创建 Swarm 实例
        swarm = self._swarm_factory.create_swarm(
            team_name=team_name,
            participant_names=participant_names,
            initial_speaker_name=initial_speaker_name,
        )

        # 准备初始消息
        initial_message: BaseChatMessage

        if is_resume:
            # --- 恢复逻辑 ---
            saved_state = await self._ctx.task_workbench.get_item(state_key)
            if not saved_state:
                return f"[SWARM_ERROR] 尝试恢复团队 '{team_name}'，但未找到任何保存的状态。"

            await swarm.load_state(saved_state)
            logger.info(f"Swarm 团队 '{team_name}' 已从保存的状态恢复。")

            # 将用户的输入包装成 HandoffMessage，交还给上一个发言者
            last_speaker = saved_state.get("current_speaker", initial_speaker_name)
            initial_message = HandoffMessage(
                source="PMCAUserProxy", target=last_speaker, content=task
            )
        else:
            # --- 初始运行逻辑 ---
            initial_message = TextMessage(source=initial_speaker_name, content=task)

        # 运行团队
        result = await swarm.run(task=initial_message)

        # --- 结果处理 ---
        if (
            result.stop_reason
            and PMCARoutingMessages.TEAM_NEED_USER.value in result.stop_reason
        ):
            # Swarm 请求用户输入，保存状态并返回信号
            state_to_save = await swarm.save_state()
            await self._ctx.task_workbench.set_item(state_key, state_to_save)
            logger.success(f"Swarm 团队 '{team_name}' 已暂停并保存状态。")
            return PMCARoutingMessages.SIGNAL_PAUSE.value
        else:
            # 任务正常完成，清理状态并返回结果
            await self._ctx.task_workbench.set_item(state_key, None)
            logger.success(f"Swarm 团队 '{team_name}' 已完成任务。")
            return result.messages[-1].content  # type: ignore
