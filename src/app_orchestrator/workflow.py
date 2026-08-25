"""Agent Framework workflow integration for the application pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from typing_extensions import Never

from agent_framework import Executor, WorkflowBuilder, WorkflowContext, handler

from .agents.compile import CompileAgent
from .agents.implementation import ImplementationAgent
from .agents.interaction import InteractionAgent
from .agents.requirement_enhancer import RequirementEnhancerAgent
from .providers import ProviderRegistry
from .state import PipelineState
from .workspace import Workspace


@dataclass
class PipelineMessage:
    """Message passed between the application workflow executors."""

    requirements: str
    results: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class InteractionExecutor(Executor):
    """Execute the application's interaction stage."""

    def __init__(
            self,
            workspace: Workspace,
            state: PipelineState,
            provider_registry: ProviderRegistry,
    ) -> None:
        super().__init__(id="interaction")

        self.agent = InteractionAgent(
            workspace,
            state,
            provider_registry,
        )

    @handler
    async def process(
            self,
            message: PipelineMessage,
            ctx: WorkflowContext[PipelineMessage],
    ) -> None:
        """Run interaction processing and forward the pipeline message."""

        result = self.agent.run()

        message.results["interaction"] = result

        await ctx.send_message(message)


class RequirementExecutor(Executor):
    """Execute the application's requirement-enhancement stage."""

    def __init__(
            self,
            workspace: Workspace,
            state: PipelineState,
            provider_registry: ProviderRegistry,
    ) -> None:
        super().__init__(id="requirement-enhancement")

        self.agent = RequirementEnhancerAgent(
            workspace,
            state,
            provider_registry,
        )

    @handler
    async def process(
            self,
            message: PipelineMessage,
            ctx: WorkflowContext[PipelineMessage],
    ) -> None:
        """Enhance requirements and forward the pipeline message."""

        result = self.agent.run()

        message.results["requirement_enhancement"] = result

        await ctx.send_message(message)


class ImplementationExecutor(Executor):
    """Execute the application's incremental implementation stage."""

    def __init__(
            self,
            workspace: Workspace,
            state: PipelineState,
            provider_registry: ProviderRegistry,
    ) -> None:
        super().__init__(id="implementation")

        self.agent = ImplementationAgent(
            workspace,
            state,
            provider_registry,
        )

    @handler
    async def process(
            self,
            message: PipelineMessage,
            ctx: WorkflowContext[PipelineMessage],
    ) -> None:
        """Generate or update the implementation and continue the pipeline."""

        result = self.agent.run()

        message.results["implementation"] = result

        await ctx.send_message(message)


class CompileExecutor(Executor):
    """Execute compilation and produce the final workflow output."""

    def __init__(
            self,
            workspace: Workspace,
            state: PipelineState,
            provider_registry: ProviderRegistry,
    ) -> None:
        super().__init__(id="compile")

        self.agent = CompileAgent(
            workspace,
            state,
            provider_registry,
        )

    @handler
    async def process(
            self,
            message: PipelineMessage,
            ctx: WorkflowContext[Never, PipelineMessage],
    ) -> None:
        """
        Compile the generated application and terminate the workflow.

        Never is used as the downstream message type because this executor
        does not send a message to another executor. PipelineMessage is the
        workflow-level output type because this executor yields the final
        pipeline result.
        """

        result = self.agent.run()

        message.results["compile"] = result

        await ctx.yield_output(message)


class ApplicationWorkflow:
    """
    Agent Framework workflow for the application orchestration pipeline.

    Existing application agents remain responsible for application/business
    logic. Agent Framework is responsible for sequencing the stages and
    exposing the workflow boundary.
    """

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

    async def run(
            self,
            requirements: str,
    ) -> PipelineMessage:
        """Run the complete application workflow."""

        message = PipelineMessage(
            requirements=requirements,
        )

        result = await self.workflow.run(message)

        outputs = result.get_outputs()

        if not outputs:
            raise RuntimeError(
                "Application workflow completed without an output."
            )

        output = outputs[-1]

        if not isinstance(output, PipelineMessage):
            raise RuntimeError(
                "Application workflow returned an unexpected output type: "
                f"{type(output).__name__}"
            )

        return output