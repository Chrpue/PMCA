"""
core/team/base.py
===================

此模块定义了一个抽象的团队基类 ``PMCATeamBase``，用于所有团队组件的基类。

在 PMCA 多智能体体系中，不同类型的团队（简单任务团队、Swarm 团队、复杂任务团队等）
都需要遵循统一的接口：能够构建底层的 ``autogen`` 团队对象，并暴露 ``run`` 方法
用于运行任务。本基类封装了上下文对象 ``PMCATaskContext``，并提供了通用的
``run`` 实现，该实现负责发送初始消息并处理终止信号。

注意：这个基类不直接依赖任何具体的团队实现，子类必须实现 ``build`` 方法来
构建实际的 ``Team`` 对象。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from autogen_agentchat.base import Team
from autogen_agentchat.messages import TextMessage

from base.runtime import PMCATaskContext
from core.team.common import PMCARoutingMessages
from base.configs import PMCASystemEnvConfig
from core.team.core_assistants import PMCAUserProxy


class PMCATeamBase(ABC):
    """团队抽象基类。

    每个具体的团队应当继承此类，并实现 :meth:`build` 方法来构建底层
    ``autogen_agentchat.teams.Team`` 实例。该基类提供了统一的 ``run``
    接口，并内置了针对用户介入的处理逻辑。它可以在控制台模式下
    自动询问用户并继续执行，也可以在服务模式下返回中断信号供上层
    捕获。团队状态会保存到 ``ctx.task_workbench`` 中，以便下次恢复。

    参数:
        ctx: 任务上下文，包含了模型工厂、工作台等运行时信息。
    """

    def __init__(self, ctx: PMCATaskContext) -> None:
        # 运行时上下文
        self._ctx = ctx
        # 子类可以覆盖 _team_name 用于状态存储键
        self._team_name: Optional[str] = None

    @property
    def team_name(self) -> str:
        """返回团队名称，用于在工作台保存状态。

        默认值为类名，子类可通过设置 ``self._team_name`` 覆盖。
        """
        return self._team_name or self.__class__.__name__

    @abstractmethod
    def build(self) -> Team:
        """构建并返回一个 ``Team`` 实例。

        子类必须实现此方法，用于构建对应类型的群聊或团队。
        """
        raise NotImplementedError

    async def _save_state(self, team: Team) -> None:
        """保存当前团队状态到工作台。

        仅当团队实现了 ``save_state`` 方法时有效。
        """
        try:
            saved = await team.save_state()
        except Exception:
            saved = None
        await self._ctx.task_workbench.set_item(f"team_state_{self.team_name}", saved)

    async def _load_state(self, team: Team) -> Optional[dict]:
        """从工作台恢复团队状态，如存在则调用 ``load_state``。"""
        saved = await self._ctx.task_workbench.get_item(f"team_state_{self.team_name}")
        if saved:
            try:
                await team.load_state(saved)
                return saved
            except Exception:
                return None
        return None

    async def _clear_state(self) -> None:
        """清除存储的团队状态。"""
        await self._ctx.task_workbench.set_item(f"team_state_{self.team_name}", None)

    async def run(self, task: str, *, is_resume: bool = False) -> str:
        """执行给定任务并返回最终的回复文本或信号。

        该方法封装了与用户交互的逻辑：当团队在执行过程中需要
        用户提供信息或暂停时，会根据运行模式（console 或 service）
        自动处理。控制台模式下会直接询问用户并继续执行；服务
        模式下则返回中断信号 ``[NEED_USER_INTERRUPT]`` 供上层处理。

        参数:
            task: 用户输入的任务描述或附加信息。
            is_resume: 指示是否为恢复模式。恢复模式下会尝试加载之前的
                团队状态并继续执行。

        返回:
            最终回复内容，或路由信号字符串（如 ``[NEED_USER_INTERRUPT]``、
            ``[USER_CANCEL]``、``[USER_PAUSE]`` 等）。
        """
        # 构建或恢复团队
        team = self.build()
        if is_resume:
            await self._load_state(team)
        # 构造初始消息，所有团队统一由用户发起
        initial_message = TextMessage(source="User", content=task)
        result = await team.run(task=initial_message)

        # 如果没有明确停止理由，则直接返回最新消息内容
        if not result.stop_reason:
            await self._clear_state()
            return result.messages[-1].content if result.messages else ""
        # 将停止原因转换为字符串，可能是集合或单个值
        reason_str = str(result.stop_reason)
        # 用户取消信号，直接终止并清理状态
        if PMCARoutingMessages.SIGNAL_CANCEL.value in reason_str:
            await self._clear_state()
            return PMCARoutingMessages.SIGNAL_CANCEL.value
        # 用户暂停信号，保存状态并返回
        if PMCARoutingMessages.SIGNAL_PAUSE.value in reason_str:
            await self._save_state(team)
            return PMCARoutingMessages.SIGNAL_PAUSE.value
        # 团队需要用户输入信号
        if PMCARoutingMessages.TEAM_NEED_USER.value in reason_str:
            # 保存当前团队状态
            await self._save_state(team)
            # 控制台模式下自动调用用户代理获取输入并继续
            if PMCASystemEnvConfig.INTERACTION_MODE == "console":
                # 上一次系统或助手消息作为提示
                prompt = result.messages[-1].content if result.messages else ""
                # 使用用户代理获取输入
                user_proxy = PMCAUserProxy()
                user_input = await user_proxy._console_input_logic(prompt, None)
                # 解析用户指令
                # 如果用户再次取消
                if user_input == PMCARoutingMessages.SIGNAL_CANCEL.value:
                    await self._clear_state()
                    return PMCARoutingMessages.SIGNAL_CANCEL.value
                # 如果用户暂停
                if user_input == PMCARoutingMessages.SIGNAL_PAUSE.value:
                    return PMCARoutingMessages.SIGNAL_PAUSE.value
                # 如果用户使用中断指令，则将新的内容作为下一次任务继续执行
                # 去掉中断前缀中的标识
                if user_input.startswith(
                    PMCARoutingMessages.SIGNAL_INTERRUPT_PREFIX.value
                ):
                    _, new_task = user_input.split(" ", 1)
                    return await self.run(new_task, is_resume=True)
                # 普通文本直接作为补充信息继续执行
                return await self.run(user_input, is_resume=True)
            else:
                # 服务模式下上交给上层系统，让前端收集用户输入
                return PMCARoutingMessages.TEAM_NEED_USER.value
        # 任务完成信号
        if PMCARoutingMessages.TASK_TERMINATE.value in reason_str:
            await self._clear_state()
            return result.messages[-1].content if result.messages else ""
        # 默认情况下返回最新消息
        await self._clear_state()
        return result.messages[-1].content if result.messages else ""

