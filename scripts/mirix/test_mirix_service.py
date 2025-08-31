import os
import sys

import pytest
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

# Ensure the repository root and packaged Mirix module are importable
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PACKAGE_ROOT = os.path.join(ROOT, "0.1.3")
for p in (ROOT, PACKAGE_ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

load_dotenv()
os.environ.setdefault(
    "GEMINI_API_KEY", "test-key"
)  # fallback to avoid immediate failure

from base.memory.factory import PMCAMirixService


@pytest.mark.parametrize(
    "agent, memories",
    [
        (
            "agent_alpha",
            [
                ("The sky is blue", "What color is the sky?", "blue"),
                ("The sun is yellow", "What color is the sun?", "yellow"),
            ],
        ),
        (
            "agent_beta",
            [
                ("Grass is green", "What color is the grass?", "green"),
            ],
        ),
    ],
)
def test_memory_round_trip(agent, memories):
    """Verify memory storage and retrieval for multiple agents."""

    console = Console(record=True)
    service = PMCAMirixService()

    table = Table(title="Mirix Memory Round Trip", show_lines=True)
    table.add_column("Agent")
    table.add_column("Question")
    table.add_column("Answer")

    for fact, question, expected in memories:
        service.add_memory(agent, fact)
        answer = service.read_memory(agent, question)
        table.add_row(agent, question, answer)
        assert expected in answer.lower()

    console.print(table)

