from autogen_agentchat.agents import AssistantAgent, UserProxyAgent
from autogen_agentchat.conditions import TextMentionTermination
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.ui import Console
from autogen_agentchat.base import Handoff
from autogen_ext.tools.mcp import SseServerParams

from base.memory.graph_memory import PMCAAgentsGraphMemory
from client import LLMFactory, ProviderType, DutyType

from base.agents.factory import PMCACombinedWorkbench

llm_client = LLMFactory.client(ProviderType.OPENAI, DutyType.BASE)


def read_knowledge_file(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            content = file.read()
            return content
    except FileNotFoundError:
        return f"文件未找到：{file_path}"
    except Exception as e:
        return f"读取文件时发生错误：{e}"


async def main():
    memory_server_params = SseServerParams(url="http://localhost:11009/sse", timeout=20)
    wb = PMCACombinedWorkbench([memory_server_params])

    # async with wb:
    # memory = PMCAAgentsGraphMemory(wb)
    memory_agent = AssistantAgent(
        "MemoryAgent",
        model_client=llm_client,
        workbench=wb,
        model_client_stream=True,
        handoffs=[Handoff(target="User", message="Transfer to User.")],
        reflect_on_tool_use=True,
        system_message="""你是一个负责知识构建的代理，你的目的是通过给定的文本信息构建知识记忆(供其他代理使用的记忆)，这种记忆是基于知识图谱的图网络，所以你必须提取知识中的实体并自动创建实体间的关系，你要合理的利用你的工具创建记忆并创建记忆关系.
你需要注意的是:
1. 在构建记忆任务时(create_memory工具)
1) 在构建知识网络之前，你需要先理解用户任务中指定的`记忆类型`，记忆类型是[Conversation, Topic, Project, Task, Issue, Configs, Finance, Todo]中的一种.
2) 每一段记忆内容需要一个标题，这个标题通常用户任务中会指定出来，若用户没有指定，需要你根据记忆内容自动提取出内容的标题.
3) 通常用户任务会为每段记忆内容设定一个元数据，用以进行记忆检索时使用.
4) 存储记忆的时候给予记忆一个容易理解的ID，ID格式设定为{代理名称}-{任务类型}-{时间}，其中时间严格按照%Y-%m-%dT%H:%M:%S格式化(严格符合ISO 8601标准)，代理名称和任务类型通常由用户指定，以英文记录.
2. 搜索记忆任务时(search_memories工具)
1) 提取用户任务中的关键词，根据关键词搜索与之相关的记忆.
2) 用户通常会指定搜索记忆的类型，若用户没有指定，需要你来帮忙理解指定，它是[Conversation, Topic, Project, Task, Issue, Configs, Finance, Todo]中的一种.

完成任务后让User决定后续动作.
""",
    )

    user_agent = UserProxyAgent(
        "User",
        description="需要的时候让用户介入给予建议或任务追溯",
        input_func=input,
    )

    termination = TextMentionTermination("APPROVE")

    team = RoundRobinGroupChat(
        [memory_agent, user_agent], termination_condition=termination
    )

    await Console(
        team.run_stream(
            # task=read_knowledge_file(
            #     "/home/chrpue/projects/memory/PMCATeamDecision/PMCATeamDecision-20250605-1.txt"
            # )
            task="你好"
        )
    )


if __name__ == "__main__":
    import asyncio
    from dotenv import load_dotenv

    load_dotenv()

    asyncio.run(main())
