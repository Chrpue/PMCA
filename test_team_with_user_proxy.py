import asyncio
import builtins
from typing import Optional, List

import pytest
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.base import Team
from autogen_agentchat.conditions import TextMentionTermination
from autogen_agentchat.messages import TextMessage, BaseChatMessage
from autogen_agentchat.base import Response

# --- 从您的项目中导入核心模块 ---
from base.runtime import PMCARuntime, PMCATaskContext
from base.configs import PMCASystemEnvConfig
from core.team.common import PMCARoutingMessages
from core.team.core_assistants import PMCAUserProxy

# 导入您最新版本的 PMCATeamBase
from core.team.engine import PMCATeamBase


# --- Mock 对象与 Pytest Fixtures ---


class MockWorkbench:
    """一个用于测试的、简单的内存工作台，以隔离测试环境。"""

    def __init__(self):
        self._storage = {}

    async def get_item(self, key: str) -> Optional[dict]:
        return self._storage.get(key)

    async def set_item(self, key: str, value: Optional[dict]) -> None:
        self._storage[key] = value


@pytest.fixture(scope="session")
async def runtime_instance() -> PMCARuntime:
    """
    【核心修正】这是一个 session 级别的异步 fixture。
    它在所有测试开始前只运行一次，初始化并返回一个可用的 PMCARuntime 实例。
    """
    runtime = PMCARuntime()
    await runtime.initialize()
    return runtime


@pytest.fixture
def task_ctx(runtime_instance: PMCARuntime) -> PMCATaskContext:
    """
    这是一个同步 fixture，它依赖于已经 await 过的 runtime_instance。
    """
    ctx = runtime_instance.create_task_context(mission="交互式分析任务")
    # ctx.task_workbench = MockWorkbench()
    return ctx


class DummyAssistant(AssistantAgent):
    """一个测试助手，在第一次响应时请求用户输入，之后返回最终答案。"""

    def __init__(self, name: str, model_client) -> None:
        super().__init__(name, model_client=model_client, system_message="")
        self._asked = False

    async def on_messages(self, messages: List[BaseChatMessage]) -> Response:
        if not self._asked:
            self._asked = True
            content = f"请提供更多信息 {PMCARoutingMessages.TEAM_NEED_USER.value}"
        else:
            user_reply = messages[-1].content
            content = f"感谢补充: '{user_reply}', 以下是结果 {PMCARoutingMessages.TASK_TERMINATE.value}"

        return Response(chat_message=TextMessage(source=self.name, content=content))


class DummyTeam(PMCATeamBase):
    """基于您最新 PMCATeamBase 的测试团队。"""

    def build(self) -> Team:
        assistant = DummyAssistant(
            "assistant", model_client=self._ctx.llm_factory.client()
        )
        user_proxy = PMCAUserProxy().build_user_proxy_assistant()

        termination = TextMentionTermination(
            PMCARoutingMessages.TEAM_NEED_USER.value
        ) | TextMentionTermination(PMCARoutingMessages.TASK_TERMINATE.value)

        return RoundRobinGroupChat(
            name="DummyTeamForTest",
            participants=[assistant, user_proxy],
            termination_condition=termination,
        )


# --- 测试用例 ---


@pytest.mark.asyncio
async def test_team_service_mode_pause_and_resume(task_ctx: PMCATaskContext):
    """
    验证在 service 模式下，团队能够正确地中断、保存状态，并通过一个新的 run 调用来恢复。
    """
    PMCASystemEnvConfig.INTERACTION_MODE = "service"

    # --- 阶段一: 启动并触发中断 ---
    team1 = DummyTeam(task_ctx)
    result1 = await team1.run("初始任务描述")

    assert result1 == PMCARoutingMessages.TEAM_NEED_USER.value
    state_key = f"team_state_{team1.team_name}"
    saved_state = await task_ctx.task_workbench.get_item(state_key)
    assert saved_state is not None

    # --- 阶段二: 恢复任务并完成 ---
    team2 = DummyTeam(task_ctx)
    user_reply = "这是补充信息"
    result2 = await team2.run(user_reply, is_resume=True)

    assert "感谢补充" in result2
    assert "这是补充信息" in result2
    assert PMCARoutingMessages.TASK_TERMINATE.value not in result2


@pytest.mark.asyncio
async def test_team_console_mode_auto_resume(monkeypatch, task_ctx: PMCATaskContext):
    """
    验证在 console 模式下，PMCATeamBase 内部的递归调用逻辑能够正确工作。
    """
    PMCASystemEnvConfig.INTERACTION_MODE = "console"
    team = DummyTeam(task_ctx)

    user_inputs = ["这是补充信息"]

    def fake_input(prompt: str = "") -> str:
        print(prompt, end="")
        response = user_inputs.pop(0)
        print(response)
        return response

    monkeypatch.setattr(builtins, "input", fake_input)

    final_result = await team.run("初始任务描述")

    assert "感谢补充" in final_result
    assert "这是补充信息" in final_result

