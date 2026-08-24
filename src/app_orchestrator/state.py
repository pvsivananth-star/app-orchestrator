"""Global state tracking for the orchestration pipeline."""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from enum import Enum
import time
import json
from pathlib import Path

class PipelineStage(Enum):
    INIT = "init"
    REQUIREMENT_CLARIFICATION = "requirement_clarification"
    REQUIREMENT_ENHANCEMENT = "requirement_enhancement"
    BUSINESS_VALIDATION = "business_validation"
    REPO_ANALYSIS = "repo_analysis"
    DEPENDENCY_SETUP = "dependency_setup"
    LOOP_A = "loop_a"
    LOOP_B = "loop_b"
    DOCUMENTATION = "documentation"
    COMMIT = "commit"
    DONE = "done"
    FAILED = "failed"

    def __str__(self):
        return self.value

@dataclass
class PipelineState:
    stage: PipelineStage = PipelineStage.INIT
    loop_a_iteration: int = 0
    loop_b_iteration: int = 0
    max_loop_a_retries: int = 5
    max_loop_b_retries: int = 2
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    start_time: float = field(default_factory=time.time)

    def add_error(self, error: str):
        self.errors.append(error)

    def increment_loop_a(self):
        self.loop_a_iteration += 1

    def increment_loop_b(self):
        self.loop_b_iteration += 1

    def should_retry_loop_a(self) -> bool:
        return self.loop_a_iteration < self.max_loop_a_retries

    def should_retry_loop_b(self) -> bool:
        return self.loop_b_iteration < self.max_loop_b_retries

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stage": self.stage.value,
            "loop_a_iteration": self.loop_a_iteration,
            "loop_b_iteration": self.loop_b_iteration,
            "errors": self.errors,
            "metadata": self.metadata,
            "start_time": self.start_time,
            "elapsed_seconds": time.time() - self.start_time,
        }

    def save(self, path: Path):
        path.write_text(json.dumps(self.to_dict(), indent=2))