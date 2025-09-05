"""
Test runner for the knowledge distillation pipeline.

This script demonstrates how to instantiate and run the ``DistillationPipeline``
for one or more agents using a configuration.  It can be executed directly
for quick experiments without modifying the main PMCA codebase.

Usage::

    python run_distillation_pipeline.py --agent PMCATeamDecision --workspace app

    python run_distillation_pipeline.py --agent all --workspace app --no-inject --topic-top-k 8 \
        --retrieval-top-k 10 --chunk-top-k 5

By default, it uses the ``default`` prompt template defined under
``base/knowledge/distill/prompts`` and writes the distilled memory into mem0.
Specify ``--no-inject`` to skip memory injection and just print the messages.
"""

import argparse
import asyncio
from typing import List

from base.knowledge.distill import PMCADistillationConfig
from base.knowledge.distill import PMCADistillationPipeline


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the knowledge distillation pipeline."
    )
    parser.add_argument(
        "--agent",
        required=True,
        help="Agent name to process or 'all' for predefined decision agents.",
    )
    parser.add_argument(
        "--workspace", default="app", help="LightRAG workspace name (default: 'app')."
    )
    parser.add_argument(
        "--template", default="default", help="Name of the prompt template to use."
    )
    parser.add_argument(
        "--topic-top-k",
        type=int,
        default=5,
        help="Number of topics to retain after discovery.",
    )
    parser.add_argument(
        "--retrieval-top-k",
        type=int,
        default=5,
        help="Number of documents to retrieve for deep dive.",
    )
    parser.add_argument(
        "--chunk-top-k",
        type=int,
        default=3,
        help="Number of chunks to retrieve for deep dive.",
    )
    parser.add_argument(
        "--no-inject",
        action="store_true",
        help="Do not write distilled memory into mem0.",
    )
    args = parser.parse_args()

    config = PMCADistillationConfig(
        template=args.template,
        topic_top_k=args.topic_top_k,
        retrieval_top_k=args.retrieval_top_k,
        chunk_top_k=args.chunk_top_k,
        inject=not args.no_inject,
    )
    pipeline = PMCADistillationPipeline(config)
    # Define default agents list
    default_agents: List[str] = [
        "PMCATeamDecision",
        "PMCAAgentsDecision",
        "PMCATeamDecisionCritic",
        "PMCAAgentsDecisionCritic",
    ]
    agents = default_agents if args.agent.lower() == "all" else [args.agent]
    results = await pipeline.run_agents(agents, args.workspace)
    for agent_name, message in results.items():
        if message:
            print(f"\n--- Injection message for {agent_name} ---\n{message}\n")
        else:
            print(f"\n--- No message generated for {agent_name} ---\n")


if __name__ == "__main__":
    asyncio.run(main())
