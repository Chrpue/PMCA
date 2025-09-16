import asyncio
from typing import List, cast
from loguru import logger

from autogen_agentchat.teams import RoundRobinGroupChat, SelectorGroupChat
from autogen_agentchat.conditions import MaxMessageTermination
from autogen_agentchat.messages import BaseChatMessage

from base.runtime import PMCATaskContext
from core.team.common.triage_models import TriageResult
from core.team.engine.selector_group import PMCASelectorGroup


class PMCATaskDispatcher:
    """
    一个统一的、可自我升级的对话入口。
    它开始于一个简单的“分诊模式”，如果任务被判定为复杂，
    它会自动“晋升”为一个由Orchestrator领导的“执行模式”。
    """

    def __init__(self, ctx: PMCATaskContext):
        self._ctx = ctx
        self._triage_team = self._build_triage_team()
        self._execution_team: SelectorGroupChat | None = None
        self._final_result = None

    def _build_triage_team(self) -> RoundRobinGroupChat:
        """构建用于任务分类的分诊团队。"""
        factory = self._ctx.assistant_factory

        # 1. 准备分诊团队的参与者
        user_proxy = factory.create_assistant("PMCAUserProxy")

        all_metas = factory.get_all_registered_assistants()
        available_executors = {
            name: meta.duty for name, meta in all_metas.items() if meta.domains
        }
        available_executors_str = "\n".join(
            [f"- {name}: {duty}" for name, duty in available_executors.items()]
        )

        classifier_meta = all_metas["PMCATaskClassifier"]
        classifier_prompt = classifier_meta.system_message.format(
            available_executors=available_executors_str, mission=self._ctx.task_mission
        )

        task_classifier = factory.create_assistant(
            biz_type="PMCATaskClassifier",
            system_message=classifier_prompt,
            output_content_type=TriageResult,
        )

        simple_responder = factory.create_assistant("PMCASimpleResponder")

        return RoundRobinGroupChat(
            participants=[user_proxy, task_classifier, simple_responder],
            termination_condition=MaxMessageTermination(max_messages=5),
        )

    async def run(self, initial_task: str):
        """
        启动任务调度器。
        """
        # --- 阶段一: 运行分诊团队 ---
        logger.info("--- 启动任务分诊层 ---")
        triage_run_result = await self._triage_team.run(task=initial_task)

        # 从结果中提取结构化的分诊决策
        triage_decision = None
        for msg in reversed(triage_run_result.messages):
            if msg.source == "PMCATaskClassifier" and isinstance(
                msg.content, TriageResult
            ):
                triage_decision = msg.content
                break

        if not triage_decision:
            logger.error("分诊失败！未能获取有效分类结果。")
            self._final_result = "抱歉，系统在分析您的任务时遇到内部错误。"
            return

        # --- 决策点: 根据分诊结果决定下一步 ---
        if triage_decision.task_type == "simple_task":
            logger.success("任务被分类为简单问答，已在前台处理。")
            for msg in reversed(triage_run_result.messages):
                if msg.source == "PMCASimpleResponder":
                    self._final_result = msg.content
                    return
            self._final_result = "简单任务已处理，但未能找到最终回复。"

        elif triage_decision.task_type == "clarification_needed":
            logger.info("任务需要澄清。")
            self._final_result = triage_decision.comment

        elif triage_decision.task_type == "complex_task":
            logger.success("任务被分类为复杂任务，正在“晋升”为执行模式...")

            # --- 阶段二: 启动执行团队 ---
            participant_names = [
                "PMCAOrchestrator",
                "PMCAUserProxy",
            ] + (triage_decision.required_executors or [])

            group_builder = PMCASelectorGroup(
                ctx=self._ctx, participant_names=participant_names
            )
            self._execution_team = group_builder.build()

            # 将初始任务传递给执行团队
            execution_run_result = await self._execution_team.run(
                task=self._ctx.task_mission
            )

            # 提取最终结果
            if execution_run_result.messages:
                self._final_result = execution_run_result.messages[-1].content
            else:
                self._final_result = "复杂任务已执行，但未产生最终结果。"

    @property
    def final_result(self):
        return self._final_result
