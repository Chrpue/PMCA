import asyncio
from loguru import logger
from typing import List, Sequence, Union, Optional

from autogen_agentchat.base import TaskResult
from autogen_agentchat.agents import AssistantAgent, UserProxyAgent
from autogen_agentchat.conditions import (
    ExternalTermination,
    MaxMessageTermination,
    TextMentionTermination,
)
from autogen_agentchat.messages import BaseAgentEvent, BaseChatMessage
from autogen_agentchat.teams import SelectorGroupChat
from autogen_agentchat.ui import Console

from core.client import LLMFactory, ProviderType


def search_web_tool(query: str) -> str:
    if "2006-2007" in query:
        return """以下是迈阿密热火队球员在 2006-2007 赛季的总得分：
        Udonis Haslem: 844 分
        Dwayne Wade: 1397 分
        James Posey: 550 分
        ...
        """
    elif "2007-2008" in query:
        return "德维恩·韦德在 2007-2008 赛季迈阿密热火队的总篮板数为 214 个。"
    elif "2008-2009" in query:
        return "德维恩·韦德在 2008-2009 赛季迈阿密热火队的总篮板数为 398 个。"
    return "未找到数据"


def percentage_change_tool(start: float, end: float) -> float:
    return ((end - start) / start) * 100


model_client = LLMFactory.client()

planning_agent = AssistantAgent(
    "PlanningAgent",
    description="An agent for planning tasks, this agent should be the first to engage when given a new task.",
    model_client=model_client,
    system_message="""
你是一名任务规划师。
你的工作是将复杂的任务分解成更小、更易于管理的子任务。
你的团队成员包括：
WebSearchAgent：搜索信息
DataAnalystAgent：执行计算

你只需规划和委派任务，无需亲自执行。

分配任务时，请使用以下格式：
1. <代理>: <任务>

当所有任务完成后，总结发现并以"TERMINATE" 结束.
""",
)

web_search_agent = AssistantAgent(
    "WebSearchAgent",
    description="An agent for searching information on the web.",
    tools=[search_web_tool],
    model_client=model_client,
    system_message="""
你是一个网络搜索代理。
你唯一的工具是 search_tool - 用它来查找信息。
你每次只能进行一次搜索。
一旦你获得了结果，你就永远不会基于结果进行任何计算。
""",
)

data_analyst_agent = AssistantAgent(
    "DataAnalystAgent",
    description="An agent for performing calculations.",
    model_client=model_client,
    tools=[percentage_change_tool],
    system_message="""
你是一名数据分析师。
根据你被分配的任务，你应该分析数据并使用提供的工具提供结果。
如果你还没有看到这些数据，请向我索取。
""",
)

text_mention_termination = TextMentionTermination("TERMINATE")
max_messages_termination = MaxMessageTermination(max_messages=25)
external_termination = ExternalTermination()

termination = text_mention_termination | max_messages_termination | external_termination

selector_prompt = """Select an agent to perform task.

{roles}

Current conversation context:
{history}

阅读以上对话，然后从 {participants} 中选择一名代理人执行下一个任务。
请确保 `任务规划师` 在其他代理人开始工作之前已分配任务。
仅选择一名代理人
"""


team = SelectorGroupChat(
    [planning_agent, web_search_agent, data_analyst_agent],
    model_client=model_client,
    termination_condition=termination,
    selector_prompt=selector_prompt,
    allow_repeated_speaker=True,  # Allow an agent to speak multiple turns in a row.
)


# ---- 打印工具：将一个事件/消息渲染为简明文本 ----
def render_item(item: Union[BaseAgentEvent, BaseChatMessage]) -> str:
    # 所有消息/事件都实现了 to_text()；另外包含 source/created_at 字段
    who = getattr(item, "source", "?")
    t = getattr(item, "created_at", None)
    kind = item.__class__.__name__
    body = item.to_text().strip()
    prefix = f"[{t}] " if t else ""
    return f"{prefix}{who} · {kind}:\n{body}"


# ---- （可选）按“轮次”分组：当说话人变化就视为新一轮 ----
class RoundPrinter:
    def __init__(self) -> None:
        self._current_speaker: Optional[str] = None
        self._buffer: List[str] = []

    def _flush(self):
        if self._buffer:
            print("\n".join(self._buffer))
            print("-" * 80)  # 分割线表示一轮结束
            self._buffer.clear()

    def feed(self, item: Union[BaseAgentEvent, BaseChatMessage]):
        speaker = getattr(item, "source", None)
        # 当遇到新的 speaker（且不是流式分片同一来源）时，视为新一轮
        if (
            self._current_speaker is not None
            and speaker
            and speaker != self._current_speaker
        ):
            self._flush()
        self._current_speaker = speaker or self._current_speaker
        self._buffer.append(render_item(item))

    def finish(self):
        self._flush()


# ---- 手动消费 team.run_stream(...) 并打印 ----
async def print_team_stream(
    team, *, task=None, output_task_messages: bool = True
) -> TaskResult:
    round_printer = RoundPrinter()
    async for item in team.run_stream(
        task=task, output_task_messages=output_task_messages
    ):
        if isinstance(item, TaskResult):
            # 打印最后一轮尚未flush的内容
            round_printer.finish()
            # 打印停止原因/统计
            print(f"STOP REASON: {item.stop_reason}")
            # 你也可以在这里访问 item.messages 做二次汇总
            return item
        else:
            # 过滤掉流式分片（可选）：若你不想看到 token 级别分片，可跳过
            if item.__class__.__name__ == "ModelClientStreamingChunkEvent":
                # 示例：忽略分片。若想聚合，可用 full_message_id 做拼接。
                continue
            round_printer.feed(item)

    # 理论上不会到这里（TaskResult 总会作为最后一项返回）
    round_printer.finish()
    raise RuntimeError("Stream ended without TaskResult")


# _running_task: asyncio.Task | None = None
#
#
# async def task_start(task):
#     global _running_task
#     _running_task = asyncio.create_task(print_team_stream(team, task=task))
#
#
# async def task_stop():
#     global _running_task
#     await asyncio.sleep(3)
#     external_termination.set()
#     if _running_task:
#         await _running_task
#         _running_task = None
#     # 显式复位所有终止条件
#     await asyncio.gather(
#         text_mention_termination.reset(),
#         max_messages_termination.reset(),
#         external_termination.reset(),
#     )
#
#
# async def task_resume():
#     await print_team_stream(team)
async def drain_and_print(stream):
    async for item in stream:
        if isinstance(item, TaskResult):
            print("STOP REASON:", item.stop_reason)
            return item
        # item 支持 to_text()；或按需用 isinstance 做更细分处理
        print(f"{item.__class__.__name__} | {getattr(item, 'source', None)}")
        print(item.to_text())


_running_task = None  # 全局/外部变量保存唯一消费者任务


async def task_start(task: str):
    global _running_task
    assert _running_task is None, "已有运行中的流"
    _running_task = asyncio.create_task(drain_and_print(team.run_stream(task=task)))


async def task_stop():
    global _running_task
    external_termination.set()  # 请求停止：当前说话轮结束后停止
    if _running_task:
        await _running_task  # ***务必等待流跑到 TaskResult 结束***
        _running_task = None
    # 稳妥起见，把 OR 过的终止条件逐个 reset（外部终止、提及终止、消息数终止）
    await asyncio.gather(
        external_termination.reset(),
        text_mention_termination.reset(),
        max_messages_termination.reset(),
    )


async def task_resume():
    # 继续上一任务（不带 task）
    await drain_and_print(team.run_stream())


async def main():
    task = "2006-2007 赛季迈阿密热火队得分最高的球员是谁？2007-2008 赛季和 2008-2009 赛季之间他的总篮板数变化百分比是多少？"

    await task_start(task=task)
    await task_stop()

    logger.error("================================================================")
    logger.error("=====================等待3秒====================================")
    logger.error("================================================================")

    await task_resume()


if __name__ == "__main__":
    asyncio.run(main())

