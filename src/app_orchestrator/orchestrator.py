"""Orchestrator – runs the application workflow."""

import asyncio
import logging
from pathlib import Path

from .providers import ProviderRegistry
from .state import PipelineStage, PipelineState
from .workflow import ApplicationWorkflow
from .workspace import Workspace

logger = logging.getLogger(__name__)


class Orchestrator:
    def __init__(self, repo_path: Path):
        self.repo_path = repo_path
        self.workspace = Workspace(repo_path)
        self.state = PipelineState()

        self.provider_registry = ProviderRegistry()
        self.provider_registry.load_config()

    async def run_async(self, requirements: str) -> dict:
        """
        Execute the application through the Agent Framework workflow.
        """

        try:
            self.workspace.write(
                "user_requirements.md",
                requirements,
            )

            logger.info(
                "Starting Agent Framework application workflow"
            )

            workflow = ApplicationWorkflow(
                workspace=self.workspace,
                state=self.state,
                provider_registry=self.provider_registry,
            )

            result = await workflow.run(requirements)

            compile_result = result.results.get(
                "compile",
                {},
            )

            compile_status = compile_result.get(
                "status",
            )

            if compile_status != "pass":
                self.state.stage = PipelineStage.FAILED

                error = (
                    "Compilation failed"
                    if compile_status == "fail"
                    else "Compilation did not produce a valid status"
                )

                self.state.add_error(error)

                self.workspace.write_json(
                    "state.json",
                    self.state.to_dict(),
                )

                return {
                    "status": "failed",
                    "error": error,
                    "compile_status": compile_status,
                    "state": self.state.to_dict(),
                }

            self.state.stage = PipelineStage.DONE

            self.workspace.write_json(
                "state.json",
                self.state.to_dict(),
            )

            return {
                "status": "success",
                "message": (
                    "Requirements → Implementation → "
                    "Compilation completed"
                ),
                "compile_status": compile_status,
                "state": self.state.to_dict(),
            }

        except Exception as exc:
            self.state.stage = PipelineStage.FAILED
            self.state.add_error(str(exc))

            logger.exception(
                "Application workflow failed"
            )

            self.workspace.write_json(
                "state.json",
                self.state.to_dict(),
            )

            return {
                "status": "failed",
                "error": str(exc),
                "state": self.state.to_dict(),
            }

    def run(self, requirements: str) -> dict:
        """
        Backward-compatible synchronous entry point.

        Existing callers do not need to know that the internal
        orchestration engine is now asynchronous.
        """

        return asyncio.run(
            self.run_async(requirements)
        )