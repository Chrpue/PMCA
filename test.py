from autogen_agentchat.agents import (
    AssistantAgent,
    MessageFilterAgent,
    MessageFilterConfig,
    PerSourceFilter,
)
from autogen_agentchat.teams import DiGraphBuilder, GraphFlow
from autogen_agentchat.ui import Console
from autogen_ext.models.openai import OpenAIChatCompletionClient

# Model client
client = OpenAIChatCompletionClient(model="gpt-4.1-nano")

# Create agents
researcher = AssistantAgent(
    "researcher",
    model_client=client,
    system_message="Summarize key facts about climate change.",
)
analyst = AssistantAgent(
    "analyst",
    model_client=client,
    system_message="Review the summary and suggest improvements.",
)
presenter = AssistantAgent(
    "presenter",
    model_client=client,
    system_message="Prepare a presentation slide based on the final summary.",
)

# Apply message filtering
filtered_analyst = MessageFilterAgent(
    name="analyst",
    wrapped_agent=analyst,
    filter=MessageFilterConfig(
        per_source=[PerSourceFilter(source="researcher", position="last", count=1)]
    ),
)

filtered_presenter = MessageFilterAgent(
    name="presenter",
    wrapped_agent=presenter,
    filter=MessageFilterConfig(
        per_source=[PerSourceFilter(source="analyst", position="last", count=1)]
    ),
)

# Build the flow
builder = DiGraphBuilder()
builder.add_node(researcher).add_node(filtered_analyst).add_node(filtered_presenter)
builder.add_edge(researcher, filtered_analyst).add_edge(
    filtered_analyst, filtered_presenter
)

# Create the flow
flow = GraphFlow(
    participants=builder.get_participants(),
    graph=builder.build(),
)

# Run the flow
await Console(flow.run_stream(task="Summarize key facts about climate change."))
