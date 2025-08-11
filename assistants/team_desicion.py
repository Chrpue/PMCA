from typing import Annotated, Union
from pydantic import BaseModel, Field
from dataclasses import dataclass
from enum import Enum

from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_ext.models.ollama import OllamaChatCompletionClient
from autogen_agentchat.messages import TextMessage
from autogen_agentchat.agents import AssistantAgent
from autogen_core import MessageContext, RoutedAgent, message_handler

from base.memory.inner_memory import PMCATeamDecision


@dataclass
class UserTaskMessage:
    content: str


class TeamComponent(str, Enum):
    MAGENTIC_ONE = "Magentic-One"
    SWARM = "Swarm"
    ROUND_ROBIN = "RoundRobin"
    GRAPH_FLOW = "GraphFlow"


# class DesicionResponse(BaseModel):
#     thought: Annotated[str, Field(description="思考过程")]
#     reason: Annotated[str, Field(description="决定的原因")]
#     team: Annotated[
#         Literal["Magentic-One", "Swarm", "RoundRobin", "GraphFlow"],
#         Field(description="选择最合适的团队组件"),
#     ]


class DesicionResponse(BaseModel):
    thought: Annotated[str, Field(description="思考过程")]
    reason: Annotated[str, Field(description="决定的原因")]
    team: Annotated[
        TeamComponent,
        Field(description="选择最合适的团队组件"),
    ]


class PMCATeamDecisionAssistant(RoutedAgent):
    def __init__(
        self,
        name: str,
        model_client: Union[OpenAIChatCompletionClient, OllamaChatCompletionClient],
    ):
        super().__init__(name)

        self._model_client = model_client
        memory = PMCATeamDecision().decision_memory
        self._delegate = AssistantAgent(
            name,
            model_client=self._model_client,
            system_message="你是一个负责结构化输出的智能体，根据用户任务描述，抉择更适合使用哪个团队组件完成任务，返回JSON结构",
            memory=[memory],
            output_content_type=DesicionResponse,
            model_client_stream=True,
        )

    @message_handler
    async def handle_message(
        self, message: UserTaskMessage, ctx: MessageContext
    ) -> None:
        print(f"智能体{self.id.type} 接收消息: {message.content}")
        response = await self._delegate.on_messages(
            [TextMessage(content=message.content, source="user")],
            ctx.cancellation_token,
        )
        print(
            # f"智能体{self.id.type} 回复消息: {response.chat_message.dump().get('content')}"
            f"智能体{self.id.type} 回复消息: {response.chat_message.content.team}"  # type: ignore
        )
