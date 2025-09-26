"""
Command‑line tool for PMCA knowledge distillation.

This script wraps the lightweight distillation pipeline defined in
``base.application.knowledge_distill.distill_pipeline`` and provides a
simple CLI for running knowledge distillation on one or more agents.
It allows control over retrieval depth, prompt templates and whether
the distilled content should be injected into the agent’s mem0 store.

The distillation process performs the following high‑level steps for
each target agent:

1. **Topic discovery** – Query LightRAG to identify a small set of
   high‑impact topics that are relevant to the agent’s domain.  This uses
   the ``topic_prompt`` from the chosen template and limits the number
   of topics with ``--topic-top-k``【347871086192137†L98-L114】.
2. **Deep retrieval & distillation** – For the discovered topics a
   detailed query is sent to LightRAG to retrieve comprehensive
   knowledge.  The retrieved answer is then passed to a large
   language model (LLM) together with a template‑driven prompt to
   produce a structured JSON profile containing persona, core
   principles, episodic and procedural memories【347871086192137†L124-L188】.
3. **Memory injection** – The profile is formatted into a human
   readable instruction message and, unless ``--dry-run`` is passed,
   injected into mem0 using ``PMCAMem0LocalService``【347871086192137†L213-L240】.  This seeds the
   agent with distilled knowledge that will inform its future
   behaviour.

Example usage::

    python distill_cli.py --agent PMCATeamDecision --workspace app

    # Process multiple agents with custom retrieval depth and no injection
    python distill_cli.py --agent all --workspace app \
        --topic-top-k 3 --retrieval-top-k 10 --chunk-top-k 5 --dry-run

Dependencies:
    - This script depends on the PMCA project being installed and
      available on the Python path.  It uses ``PMCADistillationConfig``
      and the distillation pipelines defined in
      ``base.application.knowledge_distill``.
    - Optional: ``rich`` can be installed (``pip install rich``) to
      enable the ``--rich`` flag for interactive visualisation.

"""

from __future__ import annotations

import argparse
import asyncio
from typing import List

from loguru import logger

# Import the distillation configuration and pipelines from the PMCA project.
try:
    from base.configs.knowledge_distill_config import PMCADistillationConfig
    from base.application.knowledge_distill.distill_pipeline import (
        PMCADistillationPipeline,
    )

    # The rich pipeline is optional – if rich is not installed this will
    # fail at import time.  We handle that in code below.
    from base.application.knowledge_distill.distill_pipeline_rich import (
        PMCADistillationPipelineRich,
    )
    from core.assistant.factory import PMCAAssistantFactory
except ImportError as exc:
    raise ImportError(
        "PMCA modules required for distillation are missing. Make sure the PMCA "
        "project is installed and available on the Python path."
    ) from exc


def get_decision_agents() -> List[str]:
    """Return a default list of decision agents for distillation.

    If the project adds additional decision agents in the future this
    function can be extended or replaced with dynamic discovery (e.g. by
    inspecting registrations on ``PMCAAssistantFactory``).  For now it
    returns the same default used in the earlier distillation scripts.
    """
    # We reuse the list from the old knowledge_distill script for
    # compatibility【533057008393578†L288-L296】.
    return [
        "PMCATeamDecision",
        "PMCAAgentsDecision",
        "PMCATeamDecisionCritic",
        "PMCAAgentsDecisionCritic",
    ]


async def run() -> None:
    """Entry point for the CLI.  Parses arguments and runs the pipeline."""
    parser = argparse.ArgumentParser(
        description=(
            "Run knowledge distillation for PMCA agents. This script wraps the "
            "distillation pipeline and allows control over retrieval depth, "
            "prompt templates and injection behaviour."
        ),
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
        "--template",
        "-t",
        default="default",
        help=(
            "Name of the prompt template to use (default: 'default'). "
            "Templates are located under base.application.knowledge_distill.prompts."
        ),
    )
    parser.add_argument(
        "--topic-top-k",
        type=int,
        default=5,
        help="Maximum number of topics to discover per agent (default: 5).",
    )
    parser.add_argument(
        "--retrieval-top-k",
        type=int,
        default=5,
        help="Number of chunks to retrieve from LightRAG during deep retrieval (default: 5).",
    )
    parser.add_argument(
        "--chunk-top-k",
        type=int,
        default=3,
        help="Maximum number of chunks per document to retrieve (default: 3).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="If set, do not inject the distilled memory into mem0.",
    )
    parser.add_argument(
        "--rich",
        action="store_true",
        help="If set, display intermediate steps using rich. Requires the rich library.",
    )
    args = parser.parse_args()

    # Determine which agents to process
    if args.agent.lower() == "all":
        agents = get_decision_agents()
    else:
        agents = [args.agent]

    # Build the distillation configuration
    config = PMCADistillationConfig(
        template=args.template,
        topic_top_k=args.topic_top_k,
        retrieval_top_k=args.retrieval_top_k,
        chunk_top_k=args.chunk_top_k,
        inject=not args.dry_run,
    )

    # Choose the appropriate pipeline class based on --rich flag.  We
    # attempt to import the rich pipeline above; if rich is not
    # installed this will raise and we fall back to the basic pipeline.
    pipeline_class = PMCADistillationPipeline
    if args.rich:
        try:
            # Use the rich subclass for enhanced console output
            pipeline_class = PMCADistillationPipelineRich
        except Exception:
            logger.warning(
                "Rich output requested but optional dependency missing. "
                "Falling back to standard pipeline."
            )

    # Instantiate the pipeline
    pipeline = pipeline_class(config)

    # Run the pipeline for each agent sequentially.  You could also
    # gather concurrently but sequential execution makes logs easier to
    # follow when run from the command line.
    results = await pipeline.run_agents(agents, args.workspace)

    # Print results to console
    for name, injection in results.items():
        if injection:
            logger.info(
                f"Distillation completed for {name} (message length {len(injection)} chars)"
            )
        else:
            logger.warning(
                f"Distillation failed or returned empty injection for {name}"
            )


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logger.warning("Interrupted by user.")
