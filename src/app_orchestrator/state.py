"""Global state tracking for the orchestration pipeline."""

from dataclasses import dataclass, field
from enum import Enum
import json
from pathlib import Path
import time
from typing import Any


class PipelineStage(Enum):
    INIT = "init"
    REQUIREMENT_CLARIFICATION = "requirement_clarification"
    REQUIREMENT_ENHANCEMENT = "requirement_enhancement"
    IMPLEMENTATION = "implementation"
    COMPILE = "compile"
    TEST = "test"
    LOOP_A = "loop_a"
    DONE = "done"
    FAILED = "failed"

    def __str__(self) -> str:
        return self.value


@dataclass
class PipelineState:
    stage: PipelineStage = PipelineStage.INIT
    loop_a_iteration: int = 0
    loop_b_iteration: int = 0
    max_loop_a_retries: int = 5
    max_loop_b_retries: int = 2
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    completed_stages: list[str] = field(default_factory=list)
    stage_history: list[dict[str, Any]] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)

    def transition(self, stage: PipelineStage) -> None:
        if self.stage != stage:
            self.stage_history.append(
                {
                    "stage": stage.value,
                    "timestamp": time.time(),
                }
            )
        self.stage = stage

    def complete_stage(self, stage: PipelineStage) -> None:
        name = stage.value
        if name not in self.completed_stages:
            self.completed_stages.append(name)

    def add_error(self, error: str) -> None:
        self.errors.append(error)

    def increment_loop_a(self) -> None:
        self.loop_a_iteration += 1

    def increment_loop_b(self) -> None:
        self.loop_b_iteration += 1

    def should_retry_loop_a(self) -> bool:
        return self.loop_a_iteration < self.max_loop_a_retries

    def should_retry_loop_b(self) -> bool:
        return self.loop_b_iteration < self.max_loop_b_retries

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage.value,
            "loop_a_iteration": self.loop_a_iteration,
            "loop_b_iteration": self.loop_b_iteration,
            "max_loop_a_retries": self.max_loop_a_retries,
            "max_loop_b_retries": self.max_loop_b_retries,
            "errors": self.errors,
            "metadata": self.metadata,
            "completed_stages": self.completed_stages,
            "stage_history": self.stage_history,
            "start_time": self.start_time,
            "elapsed_seconds": time.time() - self.start_time,
        }

    def save(self, path: Path) -> None:
        path.write_text(
            json.dumps(self.to_dict(), indent=2),
            encoding="utf-8",
        )