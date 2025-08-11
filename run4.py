from typing import Literal

from autogen_agentchat.messages import StructuredMessage
from autogen_agentchat.ui import Console
from autogen_agentchat.agents import AssistantAgent
from pydantic import BaseModel
from client.llm_client import LLMClient


async def main():
    # The response format for the agent as a Pydantic base model.
    class AgentResponse(BaseModel):
        thoughts: str
        response: Literal["happy", "sad", "neutral"]

    # Create an agent that uses the OpenAI GPT-4o model.
    model_client = LLMClient.get_llm_client("qwen", "base")
    agent = AssistantAgent(
        "assistant",
        model_client=model_client,
        system_message="Categorize the input as happy, sad, or neutral following the JSON format.",
        # Define the output content type of the agent.
        output_content_type=AgentResponse,
    )

    result = await Console(agent.run_stream(task="I am happy."))

    # Check the last message in the result, validate its type, and print the thoughts and response.
    assert isinstance(result.messages[-1], StructuredMessage)
    assert isinstance(result.messages[-1].content, AgentResponse)
    print("Thought: ", result.messages[-1].content.thoughts)
    print("Response: ", result.messages[-1].content.response)
    await model_client.close()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
