"""
Rich wrapper for the PMCA knowledge distillation pipeline.

This module defines ``PMCADistillationPipelineRich``, a thin subclass of
``PMCADistillationPipeline`` that augments the distillation process with
interactive Rich output.  It reuses the underlying logic from the
standard pipeline while rendering key intermediate values (topic
discovery prompt and results, deep retrieval query and answer, the
distillation prompt, distilled JSON profile and final injection) using
Rich's ``Console``, ``Panel``, ``Table`` and ``Syntax`` components.

By subclassing instead of rewriting the entire pipeline, duplication
is minimised and future changes to the base pipeline will flow
through to the rich version automatically.
"""

from __future__ import annotations

import asyncio
import json
import importlib
from typing import Dict, List, Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax

from .distill_pipeline import PMCADistillationPipeline
from base.configs import PMCADistillationConfig

try:
    from core.knowledge.factory.lightrag import PMCALightRAGClient
    from core.memory.factory.mem0 import PMCAMem0LocalService
    from core.client import LLMFactory
    from autogen_core.models import SystemMessage
    from autogen_agentchat.messages import UserMessage
    from loguru import logger
except ImportError:
    # Imports will be validated in base pipeline, so ignore here
    pass


class PMCADistillationPipelineRich(PMCADistillationPipeline):
    """A distillation pipeline that adds Rich console output to the base pipeline."""

    def __init__(
        self,
        config: PMCADistillationConfig,
        prompts_module: Optional[str] = None,
        console: Optional[Console] = None,
    ) -> None:
        super().__init__(config, prompts_module)
        # If a Console isn't provided, create a default one
        self.console = console or Console()

    async def _discover_topics(
        self, rag_client: PMCALightRAGClient, workspace: str, agent_name: str
    ) -> List[str]:
        """Override topic discovery to display the prompt and results."""
        template = self._load_template()
        prompt = template["topic_prompt"].format(agent_name=agent_name)
        # Show the prompt being sent to LightRAG
        self.console.print(
            Panel(
                prompt, title=f"Topic discovery prompt for {agent_name}", style="cyan"
            )
        )
        topics = await super()._discover_topics(rag_client, workspace, agent_name)
        # Present the discovered topics in a table
        table = Table(title=f"Discovered topics for {agent_name}")
        table.add_column("#", justify="right", style="bold cyan")
        table.add_column("Topic", style="bold white")
        for idx, topic in enumerate(topics, 1):
            table.add_row(str(idx), topic)
        self.console.print(table)
        return topics

    async def _retrieve_and_distill(
        self,
        rag_client: PMCALightRAGClient,
        llm_client,
        workspace: str,
        agent_name: str,
        topics: List[str],
    ) -> Dict[str, List[str]]:
        """Override retrieval and distillation to show queries, answers and prompts."""
        if not topics:
            return {}
        template = self._load_template()
        # Build the query exactly as in the base implementation
        query_text = (
            f"请为我提供关于以下主题的、最全面和详细的综合知识总结：{', '.join(topics)}。"
            "请整合所有相关的原则、策略、案例和工作流程。"
            f" (top_k={self.config.retrieval_top_k}, chunk_top_k={self.config.chunk_top_k})"
        )
        # Show the deep retrieval query
        self.console.print(
            Panel(
                query_text,
                title=f"Deep retrieval query for {agent_name}",
                style="magenta",
            )
        )
        # Call LightRAG with overrides as in the base implementation
        try:
            override = {
                "top_k": self.config.retrieval_top_k,
                "chunk_top_k": self.config.chunk_top_k,
            }
            result = rag_client.query(
                workspace, query_text, override_params=override, with_graph=True
            )
        except Exception as exc:
            logger.error(f"LightRAG deep query failed: {exc}")
            return {}
        if not result or not result.get("answer"):
            return {}
        rag_answer = result["answer"]
        # Display the retrieved answer
        self.console.print(
            Panel(
                rag_answer, title=f"Retrieved knowledge for {agent_name}", style="green"
            )
        )
        # Construct the distillation prompt
        distill_prompt = template["distill_prompt"].format(
            agent_name=agent_name, rag_answer=rag_answer
        )
        # Display the prompt using syntax highlighting
        syntax = Syntax(
            distill_prompt, "markdown", theme="ansi_dark", line_numbers=False
        )
        self.console.print(
            Panel(syntax, title=f"Distillation prompt for {agent_name}", style="yellow")
        )
        # Build messages and call the LLM as in the base implementation
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
        # Extract JSON from the response
        import re

        fenced = re.search(r"```json\s*(\{.*?\})\s*```", raw, re.DOTALL)
        if fenced:
            match = fenced.group(1)
        else:
            plain = re.search(r"(\{.*?\})", raw, re.DOTALL)
            match = plain.group(1) if plain else None
        if not match:
            logger.error("Failed to parse JSON from LLM response")
            return {}
        import json as _json

        try:
            profile = _json.loads(match)
        except _json.JSONDecodeError:
            logger.error("Invalid JSON returned by LLM")
            return {}
        # Ensure expected keys exist
        for key in [
            "persona",
            "core_memory_principles",
            "episodic_memories",
            "procedural_memories",
        ]:
            profile.setdefault(key, [] if key != "persona" else "")
        # Display the profile JSON nicely formatted
        profile_json = _json.dumps(profile, ensure_ascii=False, indent=2)
        self.console.print(
            Panel(
                profile_json, title=f"Distilled profile for {agent_name}", style="blue"
            )
        )
        return profile

    async def run(self, agent_name: str, workspace: str) -> str:
        """Run the pipeline for a single agent, showing the final injection message."""
        rag_client = PMCALightRAGClient()
        llm_client = LLMFactory.client()
        topics = await self._discover_topics(rag_client, workspace, agent_name)
        if not topics:
            logger.warning(f"No topics discovered for '{agent_name}'")
            return ""
        profile = await self._retrieve_and_distill(
            rag_client, llm_client, workspace, agent_name, topics
        )
        if not profile:
            logger.warning(f"Failed to distil memory profile for '{agent_name}'")
            return ""
        injection = self._build_injection(profile)
        # Display the final injection message
        self.console.print(
            Panel(
                injection,
                title=f"Injection message for {agent_name}",
                style="bright_white",
            )
        )
        if self.config.inject and injection:
            await asyncio.to_thread(
                PMCAMem0LocalService.add_memory,
                agent_name,
                injection,
                {"category": "seed", "source": f"distillation:{self.config.template}"},
            )
            logger.success(f"Injected distilled memory into mem0 for '{agent_name}'")
        return injection

    async def run_agents(
        self, agent_names: List[str], workspace: str
    ) -> Dict[str, str]:
        """Run the pipeline for multiple agents concurrently, printing each injection."""
        results: Dict[str, str] = {}

        async def _run_for(name: str) -> None:
            results[name] = await self.run(name, workspace)

        await asyncio.gather(*[_run_for(n) for n in agent_names])
        return results
