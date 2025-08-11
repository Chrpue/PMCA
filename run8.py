import asyncio
from dotenv import load_dotenv
from typing import Literal

load_dotenv()
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.ui import Console
from autogen_agentchat.tools import AgentTool, TeamTool
from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination

from base.agents.factory import PMCAAgentFactory
from base.agents import PMCACodeGenExecTool
from client.llm_factory import LLMFactory, ProviderType, DutyType
from pydantic import BaseModel, Field


class CodeExecResponse(BaseModel):
    result: str = Field(description="任务执行结果，只返回代码的执行结果")
    outcome: Literal["成功", "失败"] = Field(
        description="任务执行成功(顺利生成代码并执行代码反馈结果)，任务执行失败(在执行过程中发生错误)"
    )


llm_client = LLMFactory.client(ProviderType.QWEN, DutyType.BASE)
code_client = LLMFactory.client(ProviderType.QWEN, DutyType.CODER)

factory = PMCAAgentFactory(model_client=llm_client)


team = PMCACodeGenExecTool(model_client=llm_client)

assistant = AssistantAgent(
    name="assistant",
    model_client=llm_client,
    tools=[team.team_tool],
    system_message="""你是一个根据用户任务自动生成代码并执行的助手，任务执行结束后只汇报执行结果，不要输出任何代码或执行过程的中间信息.输出内容遵循以下格式:
**任务执行结果** (根据任务需求，反馈代码执行结果) 
""",
    reflect_on_tool_use=True,
)

executor = team.docker_exec


async def main():
    task = "随机生成30个20~50的浮点型数值，并统计其中大于30的有几个"
    await executor.start()
    await Console(assistant.run_stream(task=task))
    await executor.stop()


if __name__ == "__main__":
    asyncio.run(main())
