from loguru import logger
from typing import Sequence, AsyncGenerator
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.base import Response, TaskResult
from autogen_core import CancellationToken
from autogen_agentchat.messages import (
    BaseAgentEvent,
    BaseChatMessage,
    TextMessage,
)


from base.runtime.system_workbench import PMCATaskContext
from core.client.llm_factory import DutyType, ProviderType
from core.team.factory import PMCATeamExecutor, PMCATeamFeedBack
from core.team import PMCATeamMap
from core.team import PMCASwarm


class TeamBootstrapProxy(AssistantAgent):
    """团队任务执行代理节点，负责根据计划启动团队，并处理暂停/恢复逻辑。"""

    TEAM_STATE_KEY = "team_state"  # Workbench 键名：存储暂停时的团队状态

    def __init__(self, name: str, task_ctx: PMCATaskContext):
        super().__init__(
            name=name,
            model_client=task_ctx.llm_factory.client(
                ProviderType(task_ctx.task_model_provider),
                DutyType.BASE,
            ),
        )
        self._task_ctx = task_ctx
        self._team_factory: PMCASwarm | None = None
        self._team_executor: PMCATeamExecutor | None = None

    async def _ensure_executor(self):
        """确保已根据决策结果创建团队执行器。"""
        if self._team_executor is not None:
            return  # 团队已创建（未完成或暂停状态）
        decision_result = await self._task_ctx.task_workbench.get_item("entry_decision")
        if decision_result is None:
            raise RuntimeError("TeamBootstrapProxy: 缺少 entry_decision 决策结果")
        if not decision_result.team:
            raise RuntimeError("TeamBootstrapProxy: 决策结果中没有团队组件类型")
        if not decision_result.partners:
            raise RuntimeError("TeamBootstrapProxy: 决策结果中没有候选智能体列表")
        # 根据决策选择团队组件类，创建团队工厂
        cls = PMCATeamMap.get(decision_result.team)
        if cls is None:
            raise ValueError(
                f"TeamBootstrapProxy: 未知的团队组件类型: {decision_result.team}"
            )
        # 实例化团队工厂（创建团队及其智能体）
        self._team_factory = cls(self._cfg.factory, self._llm_cfg.model_client)
        # 构建团队执行器，准备运行任务
        self._team_executor = PMCATeamExecutor(
            decision_result.partners, self._team_factory
        )

        # term = TextMentionTermination(TeamFeedBack.NEEDUSER)
        # team = self._team_executor.team_component

        # try:
        #     team._termination_condition = getattr(team, "termination_condition", None) or self._team_factory._external_termination
        #     team._termination_condition = team._termination_condition | term
        # except Exception as e:
        #     logger.warning(f"Failed to set termination condition on team: {e}")

        # 可选：设置终止条件，比如当输出 "NEEDUSER" 时暂停
        # 如果 PMCASwarm 支持传入 termination_condition，可在此配置：
        # self._team_factory.team.termination_condition = TextMentionTermination(TeamFeedBack.NEEDUSER)

    async def on_messages_stream(
        self, messages: Sequence[BaseChatMessage], cancellation_token: CancellationToken
    ) -> AsyncGenerator[BaseAgentEvent | BaseChatMessage | Response, None]:
        await self._ensure_executor()
        last_msg = messages[-1]

        # 当需要用户介入的时候
        if last_msg.source.startswith(
            "PMCAUserProxy"
        ) and await self._cfg.app_workbench.get_item(self.TEAM_STATE_KEY):
            # 获取最后一条信息(最后一条信息为用户输入信息)
            user_reply = last_msg.content  # type: ignore

            # 加载team state
            state = await self._cfg.app_workbench.get_item(self.TEAM_STATE_KEY)
            if state:
                await self._team_executor.team_component.load_state(state)

            # 删除team state
            await self._cfg.app_workbench.set_item(self.TEAM_STATE_KEY, None)

            # 根据用户追溯继续团队任务
            # 重置CancellationToken
            self._team_factory.cancellation_token = CancellationToken()

            next_msg = TextMessage(source="PMCAUserProxy", content=user_reply)
            async for event in self._team_executor.team_component.run_stream(
                task=next_msg, cancellation_token=self._team_factory.cancellation_token
            ):
                if isinstance(event, BaseChatMessage):
                    # if TeamFeedBack.FINISHED in event.content:
                    #     continue
                    yield event  # forward team messages during resume
                elif isinstance(event, TaskResult):
                    if PMCATeamFeedBack.NEEDUSER in (event.stop_reason or ""):
                        # Team again needs user input
                        # Pause state and ask user (loop back in GraphFlow)
                        await self._cfg.app_workbench.set_item(
                            self.TEAM_STATE_KEY,
                            await self._team_executor.team_component.save_state(),
                        )
                        yield Response(
                            chat_message=TextMessage(
                                source=self.name, content=PMCATeamFeedBack.NEEDUSER
                            )
                        )
                        return
                    elif PMCATeamFeedBack.FINISHED in (event.stop_reason or ""):
                        yield Response(
                            chat_message=TextMessage(
                                source=self.name, content=PMCATeamFeedBack.FINISHED
                            )
                        )

                        await self._cfg.app_workbench.set_item(
                            self.TEAM_STATE_KEY, None
                        )

                        continue

            try:
                await self._team_executor.team_component.reset()
            finally:
                self._team_executor = None
                self._team_factory = None
            return

        # 当处理新任务的时候
        task_description = messages[0].content  # type: ignore
        logger.info(f"Starting team task: {task_description}")
        # Run the team until completion or pause
        self._team_factory.cancellation_token = CancellationToken()
        async for event in self._team_executor.team_component.run_stream(
            task=task_description,
            cancellation_token=self._team_factory.cancellation_token,
        ):
            if isinstance(event, BaseChatMessage):
                yield event  # stream out the agent/tool messages
            elif isinstance(event, TaskResult):
                # Run ended (either finished or paused by NEEDUSER)
                if PMCATeamFeedBack.NEEDUSER in (event.stop_reason or ""):
                    # Save state for later resume
                    await self._cfg.app_workbench.set_item(
                        self.TEAM_STATE_KEY,
                        await self._team_executor.team_component.save_state(),
                    )
                    # Ask user for input (GraphFlow will route this to user)
                    yield Response(
                        chat_message=TextMessage(
                            source=self.name, content=PMCATeamFeedBack.NEEDUSER
                        )
                    )
                    return  # pause execution here
                elif PMCATeamFeedBack.FINISHED in (event.stop_reason or ""):
                    yield Response(
                        chat_message=TextMessage(
                            source=self.name, content=PMCATeamFeedBack.FINISHED
                        )
                    )

                    await self._cfg.app_workbench.set_item(self.TEAM_STATE_KEY, None)
                    continue
        # If we reach here, the task finished without needing user input
        # yield Response(
        #     chat_message=TextMessage(source=self.name, content=TeamFeedBack.FINISHED)
        # )
        # Reset team for next task
        try:
            await self._team_executor.team_component.reset()
        finally:
            self._team_executor = None
            self._team_factory = None

    async def on_messages(
        self, messages: Sequence[BaseChatMessage], cancellation_token: CancellationToken
    ) -> Response:
        # 顺序获取流式结果，仅返回最终的 Response
        async for ev in self.on_messages_stream(messages, cancellation_token):
            if isinstance(ev, Response):
                return ev
        # 理论上应当在流中产生 Response；若未产生，则抛出异常
        raise RuntimeError("TeamBootstrapProxy: 未产生最终 Response")

    async def on_reset(self, cancellation_token: CancellationToken):
        """在整个 GraphFlow 重置时清理内部状态。"""
        if self._team_executor:
            try:
                if hasattr(self._team_executor.team_component, "reset"):
                    await self._team_executor.team_component.reset()
            finally:
                self._team_executor = None
                self._team_factory = None
