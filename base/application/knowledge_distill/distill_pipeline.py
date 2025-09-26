"""
Distillation pipeline for PMCA knowledge base.

This module defines a ``DistillationPipeline`` class that orchestrates
topic discovery, deep knowledge retrieval, prompt generation, LLM
distillation and memory injection using configurable parameters.  It
is designed to be lightweight and easily integrated into the PMCA
multi-agent architecture without relying on heavy workflow engines.

Example usage::

    from base.knowledge.distill.pipeline import DistillationPipeline
    from base.knowledge.distill.config import DistillationConfig

    config = DistillationConfig(
        template="default",
        topic_top_k=5,
        retrieval_top_k=5,
        chunk_top_k=3,
        inject=True,
    )
    pipeline = DistillationPipeline(config)
    await pipeline.run("PMCATeamDecision", "app")

The pipeline will load the appropriate prompt templates, query
LightRAG for topics and detailed knowledge, send a prompt to the LLM
to produce a structured memory profile, and finally inject the
distilled knowledge into mem0.
"""

import asyncio
import json
import os
import importlib
from dataclasses import dataclass
from typing import Dict, List, Optional

from loguru import logger

from base.configs.knowledge_distill_config import PMCADistillationConfig

try:
    from core.knowledge.factory.lightrag import PMCALightRAGClient
    from core.memory.factory.mem0 import PMCAMem0LocalService
    from core.client import LLMFactory
    from autogen_core.models import SystemMessage
    from autogen_agentchat.messages import UserMessage
except ImportError as exc:
    raise ImportError(
        "Failed to import project modules for distillation pipeline. "
        "Ensure the PMCA environment is installed correctly."
    ) from exc


class PMCADistillationPipeline:
    """A lightweight, configurable pipeline for knowledge distillation."""

    def __init__(
        self, config: PMCADistillationConfig, prompts_module: Optional[str] = None
    ) -> None:
        self.config = config
        # Base module path where prompt templates reside.  By default
        # this points to ``base.knowledge.distill.prompts``.  You can
        # override it by providing ``prompts_module``.
        self.prompts_module_base = prompts_module or "base.prompts.knowledge_distill"
        # Cache loaded templates
        self._templates: Dict[str, Dict[str, str]] = {}

    def _load_template(self) -> Dict[str, str]:
        """
        Dynamically import a prompt template module and return its values.

        Template modules are Python files located under the module path
        specified by ``self.prompts_module_base``.  Each module must
        define ``topic_prompt`` and ``distill_prompt`` strings.  The
        loaded values are cached to avoid repeated imports.
        """
        name = self.config.template
        if name in self._templates:
            return self._templates[name]
        module_name = f"{self.prompts_module_base}.{name}"
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError as exc:
            raise FileNotFoundError(
                f"Prompt template module '{module_name}' not found"
            ) from exc
        try:
            topic_prompt = getattr(module, "topic_prompt")
            distill_prompt = getattr(module, "distill_prompt")
        except AttributeError as exc:
            raise AttributeError(
                f"Template module '{module_name}' is missing required attributes"
            ) from exc
        template_dict = {"topic_prompt": topic_prompt, "distill_prompt": distill_prompt}
        self._templates[name] = template_dict
        return template_dict

    async def _discover_topics(
        self, rag_client: PMCALightRAGClient, workspace: str, agent_name: str
    ) -> List[str]:
        """Discover relevant topics for an agent using LightRAG."""
        template = self._load_template()
        prompt = template["topic_prompt"].format(agent_name=agent_name)
        try:
            result = rag_client.query(workspace, prompt, with_graph=False)
        except Exception as exc:
            logger.error(f"LightRAG topic query failed: {exc}")
            return []
        if not result or not result.get("answer"):
            return []
        topics = [t.strip() for t in result["answer"].split(",") if t.strip()]
        # Respect topic_top_k
        return topics[: self.config.topic_top_k]

    async def _retrieve_and_distill(
        self,
        rag_client: PMCALightRAGClient,
        llm_client,
        workspace: str,
        agent_name: str,
        topics: List[str],
    ) -> Dict[str, List[str]]:
        """Retrieve knowledge from LightRAG and distil it via LLM."""
        if not topics:
            return {}
        template = self._load_template()
        # For demonstration, we embed retrieval_top_k and chunk_top_k as context
        query_text = (
            f"请为我提供关于以下主题的、最全面和详细的综合知识总结：{', '.join(topics)}。"
            "请整合所有相关的原则、策略、案例和工作流程。"
            f" (top_k={self.config.retrieval_top_k}, chunk_top_k={self.config.chunk_top_k})"
        )
        try:
            # Override base retrieval parameters using config
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
        # Build distillation prompt from template
        distill_prompt = template["distill_prompt"].format(
            agent_name=agent_name, rag_answer=rag_answer
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
        # Extract JSON from LLM response
        match = None
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
        try:
            profile = json.loads(match)
        except json.JSONDecodeError:
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
        return profile

    def _build_injection(self, profile: Dict[str, List[str]]) -> str:
        """Compose a human-readable injection message from distilled profile."""
        if not profile:
            return ""
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
        header = (
            "请为我植入初始记忆。这对我至关重要，请确保完全理解并存储以下所有信息。"
        )
        return f"{header}\n\n" + "\n\n".join(parts)

    async def run(self, agent_name: str, workspace: str) -> str:
        """
        Run the distillation pipeline for a single agent.

        Returns the injection message.  Depending on configuration, it
        may also write the message into mem0.
        """
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
        """
        Run the pipeline for multiple agents concurrently.

        Returns a dictionary mapping agent names to their injection messages.
        """
        results: Dict[str, str] = {}

        async def _run_for(agent: str) -> None:
            inj = await self.run(agent, workspace)
            results[agent] = inj

        await asyncio.gather(*[_run_for(name) for name in agent_names])
        return results
