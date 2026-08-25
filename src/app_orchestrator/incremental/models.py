"""Data models for incremental generation."""

from dataclasses import dataclass, field
from typing import Dict, List, Any
import time


@dataclass
class CodeChunk:
    """One logical implementation unit."""

    chunk_id: str
    file_path: str
    description: str
    order: int

    target_kb: float = 1.0

    dependencies: List[str] = field(
        default_factory=list
    )

    generated: bool = False
    verified: bool = False
    iterations: int = 0


@dataclass
class GenerationPlan:
    """Complete incremental implementation plan."""

    language: str
    framework: str

    chunks: List[CodeChunk] = field(
        default_factory=list
    )

    requirements_summary: str = ""

    created_at: float = field(
        default_factory=time.time
    )

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )


@dataclass
class GenerationResult:
    """Result of incremental generation."""

    status: str

    files_created: List[str] = field(
        default_factory=list
    )

    files_modified: List[str] = field(
        default_factory=list
    )

    chunks_completed: int = 0
    chunks_total: int = 0

    iterations: int = 0

    errors: List[str] = field(
        default_factory=list
    )

    duration_seconds: float = 0.0
