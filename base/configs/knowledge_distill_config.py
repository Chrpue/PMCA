"""
Configuration definitions for the knowledge distillation subsystem.

This module defines a dataclass for configuring how the distillation
pipeline operates.  The configuration can be loaded from a YAML/JSON
file or constructed programmatically.  It includes parameters for
retrieval depth, prompt templates, and memory injection behaviour.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class PMCADistillationConfig:
    """Configuration for running a knowledge distillation pipeline."""

    template: str = "default"

    topic_top_k: int = 5

    retrieval_top_k: int = 5
    chunk_top_k: int = 3

    extra: Dict[str, str] = field(default_factory=dict)

    inject: bool = True
