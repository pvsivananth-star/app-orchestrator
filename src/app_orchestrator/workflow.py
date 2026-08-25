"""Agent Framework workflow for reliable incremental execution."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any
from typing_extensions import Never

from agent_framework import Executor, WorkflowBuilder, WorkflowContext, handler

from .agents.compile import CompileAgent
from .agents.implementation import ImplementationAgent
from .agents.interaction import InteractionAgent
from .agents.requirement_enhancer import RequirementEnhancerAgent
from .providers import ProviderRegistry
from .state import PipelineStage, PipelineState
from .workspace import Workspace


@dataclass
class PipelineMessage:
    """Message passed between workflow stages."""

    requirements: str
    results: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class InteractionExecutor(Executor):
    def __init__(self, workspace, state, provider_registry):
        super().__init__(id="interaction")
        self.agent = InteractionAgent(workspace, state, provider_registry)
        self.state = state

    @handler
    async def process(
            self,
            message: PipelineMessage,
            ctx: WorkflowContext[PipelineMessage],
    ) -> None:
        self.state.transition(PipelineStage.REQUIREMENT_CLARIFICATION)
        result = await asyncio.to_thread(self.agent.run)
        message.results["interaction"] = result
        self.state.complete_stage(PipelineStage.REQUIREMENT_CLARIFICATION)
        await ctx.send_message(message)


class RequirementExecutor(Executor):
    def __init__(self, workspace, state, provider_registry):
        super().__init__(id="requirement-enhancement")
        self.agent = RequirementEnhancerAgent(
            workspace,
            state,
            provider_registry,
        )
        self.state = state

    @handler
    async def process(
            self,
            message: PipelineMessage,
            ctx: WorkflowContext[PipelineMessage],
    ) -> None:
        self.state.transition(PipelineStage.REQUIREMENT_ENHANCEMENT)
        result = await asyncio.to_thread(self.agent.run)
        message.results["requirement_enhancement"] = result
        self.state.complete_stage(PipelineStage.REQUIREMENT_ENHANCEMENT)
        await ctx.send_message(message)


class ImplementationExecutor(Executor):
    def __init__(self, workspace, state, provider_registry):
        super().__init__(id="implementation")
        self.agent = ImplementationAgent(
            workspace,
            state,
            provider_registry,
        )
        self.state = state

    @handler
    async def process(
            self,
            message: PipelineMessage,
            ctx: WorkflowContext[PipelineMessage],
    ) -> None:
        self.state.transition(PipelineStage.IMPLEMENTATION)
        result = await asyncio.to_thread(self.agent.run)
        message.results["implementation"] = result
        self.state.complete_stage(PipelineStage.IMPLEMENTATION)
        await ctx.send_message(message)


class CompileExecutor(Executor):
    def __init__(self, workspace, state, provider_registry):
        super().__init__(id="compile")
        self.agent = CompileAgent(
            workspace,
            state,
            provider_registry,
        )
        self.state = state

    @handler
    async def process(
            self,
            message: PipelineMessage,
            ctx: WorkflowContext[Never, PipelineMessage],
    ) -> None:
        self.state.transition(PipelineStage.COMPILE)

        try:
            result = await asyncio.to_thread(self.agent.run)
            message.results["compile"] = result

            if result.get("status") == "pass":
                self.state.complete_stage(PipelineStage.COMPILE)
                self.state.transition(PipelineStage.DONE)
            else:
                self.state.transition(PipelineStage.FAILED)

        except Exception as exc:
            self.state.add_error(str(exc))
            self.state.transition(PipelineStage.FAILED)
            message.error = str(exc)
            message.results["compile"] = {
                "status": "fail",
                "error": str(exc),
            }

        await ctx.yield_output(message)


class ApplicationWorkflow:
    """Reliable Agent Framework application workflow."""

    def __init__(
            self,
            workspace: Workspace,
            state: PipelineState,
            provider_registry: ProviderRegistry,
    ) -> None:
        self.workspace = workspace
        self.state = state
        self.provider_registry = provider_registry

        self.interaction = InteractionExecutor(
            workspace,
            state,
            provider_registry,
        )
        self.requirement = RequirementExecutor(
            workspace,
            state,
            provider_registry,
        )
        self.implementation = ImplementationExecutor(
            workspace,
            state,
            provider_registry,
        )
        self.compile = CompileExecutor(
            workspace,
            state,
            provider_registry,
        )

        self.workflow = (
            WorkflowBuilder(
                start_executor=self.interaction,
                output_from=[self.compile],
            )
            .add_chain(
                [
                    self.interaction,
                    self.requirement,
                    self.implementation,
                    self.compile,
                ]
            )
            .build()
        )

    async def run(self, requirements: str) -> PipelineMessage:
        """Run the workflow with bounded implementation retries."""

        message = PipelineMessage(requirements=requirements)

        for attempt in range(self.state.max_loop_a_retries + 1):
            self.state.loop_a_iteration = attempt

            if attempt:
                self.state.transition(PipelineStage.LOOP_A)

            try:
                result = await self.workflow.run(message)
            except Exception as exc:
                self.state.add_error(str(exc))
                self.state.transition(PipelineStage.FAILED)
                message.error = str(exc)
                break

            outputs = result.get_outputs()

            if not outputs:
                self.state.add_error("Workflow produced no output.")
                self.state.transition(PipelineStage.FAILED)
                message.error = "Workflow produced no output."
                break

            output = outputs[-1]

            if not isinstance(output, PipelineMessage):
                self.state.add_error(
                    f"Unexpected workflow output: {type(output).__name__}"
                )
                self.state.transition(PipelineStage.FAILED)
                message.error = "Unexpected workflow output type."
                break

            message = output
            compile_result = message.results.get("compile", {})

            if compile_result.get("status") == "pass":
                self.state.transition(PipelineStage.DONE)
                break

            if attempt >= self.state.max_loop_a_retries:
                self.state.transition(PipelineStage.FAILED)
                message.error = "Maximum implementation retries exceeded."
                self.state.add_error(message.error)
                break

        self.workspace.write_json(
            "state.json",
            self.state.to_dict(),
        )

        return message