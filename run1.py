import asyncio
from typing import List

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.base import TaskResult
from autogen_agentchat.conditions import ExternalTermination, TextMentionTermination
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_core.model_context import UnboundedChatCompletionContext
from autogen_core.models import AssistantMessage, LLMMessage, ModelFamily
from autogen_agentchat.ui import Console
from autogen_core import CancellationToken
from autogen_ext.models.openai import OpenAIChatCompletionClient
from client.llm_client import LLMClient


class ReasoningModelContext(UnboundedChatCompletionContext):
    """A model context for reasoning models."""

    async def get_messages(self) -> List[LLMMessage]:
        messages = await super().get_messages()
        # Filter out thought field from AssistantMessage.
        messages_out: List[LLMMessage] = []
        print("*****************************************")
        print(messages)
        print("*****************************************")

        for message in messages:
            if isinstance(message, AssistantMessage):
                message.thought = None
            messages_out.append(message)
        return messages_out


model_client = LLMClient.get_llm_client("qwen", "base")
# Create the primary agent.
primary_agent = AssistantAgent(
    "primary",
    model_client=model_client,
    system_message="You are a helpful AI assistant.",
    model_client_stream=True,
    model_context=ReasoningModelContext(),
)

# Create the critic agent.
critic_agent = AssistantAgent(
    "critic",
    model_client=model_client,
    system_message="Provide constructive feedback. Respond with 'APPROVE' to when your feedbacks are addressed.",
    model_client_stream=True,
    model_context=ReasoningModelContext(),
)

# Define a termination condition that stops the task if the critic approves.
text_termination = TextMentionTermination("APPROVE")

# Create a team with the primary and critic agents.
team = RoundRobinGroupChat(
    [primary_agent, critic_agent], termination_condition=text_termination, max_turns=3
)

if __name__ == "__main__":
    import asyncio

    asyncio.run(Console(team.run_stream(task="帮我写一首关于秋天的诗")))
