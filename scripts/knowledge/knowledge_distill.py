"""
knowledge_distill_mem0_rich.py
-----------------------------

This version of the knowledge distillation script adds rich console
visualisation so that you can see each step of the distillation
process.  It prints discovered topics, the deep dive query sent to
LightRAG, the distillation prompt sent to the LLM, the resulting
memory profile and the final injection message.  These are displayed
using panels, tables and syntax highlighting via the ``rich`` library
for improved readability.

Usage:

    python knowledge_distill_mem0_rich.py --agent PMCATeamDecision --workspace app

Add ``--dry-run`` to skip writing to mem0 and just view the distilled
content.  If ``--agent all`` is used, the script will iterate over
all decision agents.

This script depends on ``rich`` (``pip install rich``) and shares
logic with ``knowledge_distill_mem0_revised.py`` for core distillation.

"""

import argparse
import asyncio
import json
import re
from typing import Dict, List, Optional

from loguru import logger
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.syntax import Syntax

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    # Environment variables can still be set without dotenv
    pass

try:
    from core.knowledge.factory import PMCALightRAGClient
    from core.memory.factory import PMCAMem0LocalService
    from client import LLMFactory, ProviderType, DutyType
    from autogen_agentchat.messages import UserMessage
    from autogen_core.models import SystemMessage
except ImportError as exc:
    raise ImportError(
        "Failed to import project modules. Ensure that this script resides in your PMCA "
        "project and that all dependencies are installed."
    ) from exc

# Instantiate a global console for rich output
console = Console()


def extract_json_from_response(raw_response: str) -> Optional[str]:
    """Extract JSON from an LLM response, handling optional Markdown fences."""
    fenced = re.search(r"```json\s*(\{.*?\})\s*```", raw_response, re.DOTALL)
    if fenced:
        return fenced.group(1)
    plain = re.search(r"(\{.*?\})", raw_response, re.DOTALL)
    return plain.group(1) if plain else None


async def discover_topics(
    rag_client: PMCALightRAGClient, workspace: str, agent_name: str
) -> List[str]:
    """Query LightRAG for topics related to an agent."""
    prompt = (
        f"基于你拥有的全部知识，请列出与 '{agent_name}' 智能体的核心职责、决策策略和工作流最相关的核心主题关键词。"
        "请只返回关键词列表，用逗号分隔。"
    )
    try:
        result = rag_client.query(workspace, prompt, with_graph=False)
    except Exception as exc:
        logger.error(f"LightRAG topic query failed: {exc}")
        return []
    if not result or not result.get("answer"):
        return []
    topics = [topic.strip() for topic in result["answer"].split(",") if topic.strip()]
    # Show the topics using a rich table
    table = Table(title=f"Discovered Topics for {agent_name}")
    table.add_column("#", style="cyan", no_wrap=True)
    table.add_column("Topic", style="magenta")
    for idx, t in enumerate(topics, 1):
        table.add_row(str(idx), t)
    console.print(table)
    return topics


async def deep_dive_and_distill(
    rag_client: PMCALightRAGClient,
    llm_client,
    workspace: str,
    agent_name: str,
    topics: List[str],
) -> Dict[str, List[str]]:
    """Retrieve deep knowledge and distil into a memory profile."""
    if not topics:
        return {}
    query_text = (
        f"请为我提供关于以下主题的、最全面和详细的综合知识总结：{', '.join(topics)}。"
        "请整合所有相关的原则、策略、案例和工作流程。"
    )
    # Print the deep dive query
    console.print(
        Panel(
            f"[bold]Deep Dive Query:[/bold]\n{query_text}",
            title="LightRAG Query",
            subtitle=agent_name,
        )
    )
    try:
        result = rag_client.query(workspace, query_text, with_graph=True)
    except Exception as exc:
        logger.error(f"LightRAG deep dive query failed: {exc}")
        return {}
    if not result or not result.get("answer"):
        return {}
    rag_answer = result["answer"]
    # Prepare and show the distillation prompt
    distill_prompt = f"""
你是一位顶级的认知架构师。你的任务是为名为 '{agent_name}' 的AI智能体，根据下方由LightRAG提供的深度知识，生成一个结构化的JSON记忆档案。
这个JSON档案必须包含以下四个键：'persona', 'core_memory_principles', 'episodic_memories', 'procedural_memories'。

1.  `persona`: 提炼一句（不超过50字）关于该智能体核心身份、使命和性格的第一人称描述。
2.  `core_memory_principles`: 提炼出3-5条该智能体必须遵守的、永恒不变的核心原则或真理。这是一个字符串列表。
3.  `episodic_memories`: 将知识中的具体案例或场景，转化为1-3条“我记得一个经验/案例...”形式的第一人称情景记忆。这是一个字符串列表。
4.  `procedural_memories`: 将知识中的工作流程，提炼成1-2条“当处理...任务时，我的标准流程是：...”形式的第一人称程序性记忆。这是一个字符串列表。

如果某个类型的记忆在提供的知识中不适用或无法提炼，请返回一个空列表 `[]`。
请严格按照JSON格式输出，不要包含任何额外的解释或Markdown标记。

[LightRAG 提供的深度知识]
{rag_answer}
"""
    console.print(
        Panel(
            Syntax(distill_prompt, "python", theme="monokai", line_numbers=False),
            title="Distillation Prompt",
            subtitle=agent_name,
        )
    )
    messages = [
        SystemMessage(
            content="You are a helpful AI assistant that only responds with valid JSON."
        ),
        UserMessage(content=distill_prompt, source="memory_architect"),
    ]
    try:
        llm_response = await llm_client.create(messages=messages)
    except Exception as exc:
        logger.error(f"LLM request failed: {exc}")
        return {}
    raw = getattr(llm_response, "content", "")
    json_str = extract_json_from_response(raw)
    if not json_str:
        logger.error("Failed to extract JSON from LLM output.")
        return {}
    try:
        profile = json.loads(json_str)
    except json.JSONDecodeError:
        logger.error("LLM returned invalid JSON.")
        return {}
    for key in [
        "persona",
        "core_memory_principles",
        "episodic_memories",
        "procedural_memories",
    ]:
        profile.setdefault(key, [] if key != "persona" else "")
    # Display the distilled profile using a rich panel and table
    prof_panel = Panel(
        f"Persona: [bold]{profile['persona']}\n\n"
        f"Core Principles:\n"
        + "\n".join(f"  - {p}" for p in profile["core_memory_principles"])
        + "\n\n"
        f"Episodic Memories:\n"
        + "\n".join(f"  - {e}" for e in profile["episodic_memories"])
        + "\n\n"
        f"Procedural Memories:\n"
        + "\n".join(f"  - {p}" for p in profile["procedural_memories"]),
        title=f"Distilled Memory Profile ({agent_name})",
        border_style="green",
    )
    console.print(prof_panel)
    return profile


def build_injection_message(profile: Dict[str, List[str]]) -> str:
    """Compose a human‑readable memory injection message from a profile."""
    parts: List[str] = []
    if profile.get("persona"):
        parts.append(f"**我的核心身份 (Persona):**\n{profile['persona']}")
    if profile.get("core_memory_principles"):
        principles = "\n".join(f"- {p}" for p in profile["core_memory_principles"])
        parts.append(f"**我必须遵守的核心原则:**\n{principles}")
    if profile.get("episodic_memories"):
        episodes = "\n".join(f"- {e}" for e in profile["episodic_memories"])
        parts.append(f"**我需要记住的关键经验和案例:**\n{episodes}")
    if profile.get("procedural_memories"):
        procedures = "\n".join(f"- {p}" for p in profile["procedural_memories"])
        parts.append(f"**我需要掌握的标准操作流程:**\n{procedures}")
    if not parts:
        return ""
    header = "请为我植入初始记忆。这对我至关重要，请确保完全理解并存储以下所有信息。"
    return f"{header}\n\n" + "\n\n".join(parts)


async def seed_memory_via_mem0(
    agent_name: str,
    injection_message: str,
    dry_run: bool = False,
) -> None:
    """Write the injection message into mem0 using EnhancedMem0Service."""
    if not injection_message or len(injection_message) < 150:
        logger.warning(f"No valid injection payload for '{agent_name}'. Skipping.")
        return
    # Display the injection message in a rich panel
    console.print(
        Panel(
            injection_message,
            title=f"Injection Message for {agent_name}",
            border_style="blue",
        )
    )
    if dry_run:
        logger.info(f"[Dry Run] Not writing memory for '{agent_name}'.")
        return
    try:
        await asyncio.to_thread(
            PMCAMem0LocalService.add_memory,
            agent_name,
            injection_message,
            {"category": "seed", "source": "knowledge_distillation"},
        )
        logger.success(f"Injected distilled memory into mem0 for '{agent_name}'.")
    except Exception as exc:
        logger.error(f"Failed to inject memory for '{agent_name}': {exc}")


async def run_pipeline(agent_name: str, workspace: str, dry_run: bool) -> None:
    """Run the full distillation and seeding pipeline for a single agent."""
    rag_client = PMCALightRAGClient()
    llm_client = LLMFactory.client(ProviderType.DEEPSEEK, DutyType.BASE)
    console.rule(f"[bold yellow]Processing {agent_name}")
    topics = await discover_topics(rag_client, workspace, agent_name)
    if not topics:
        logger.warning(f"No topics discovered for '{agent_name}'.")
        return
    profile = await deep_dive_and_distill(
        rag_client, llm_client, workspace, agent_name, topics
    )
    if not profile:
        logger.warning(f"Failed to distil memory profile for '{agent_name}'.")
        return
    injection_message = build_injection_message(profile)
    await seed_memory_via_mem0(agent_name, injection_message, dry_run=dry_run)


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Distil knowledge from LightRAG and seed it into mem0 for PMCA agents with rich visualisation.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--agent",
        "-a",
        required=True,
        help="Agent name to process or 'all' to process all decision agents.",
    )
    parser.add_argument(
        "--workspace",
        "-w",
        default="app",
        help="LightRAG workspace name (default: 'app').",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the injection payload instead of adding to mem0.",
    )
    args = parser.parse_args()
    decision_agents = [
        "PMCATeamDecision",
        "PMCAAgentsDecision",
        "PMCATeamDecisionCritic",
        "PMCAAgentsDecisionCritic",
    ]
    targets = decision_agents if args.agent.lower() == "all" else [args.agent]
    for agent in targets:
        await run_pipeline(agent, args.workspace, args.dry_run)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("Interrupted by user.")
