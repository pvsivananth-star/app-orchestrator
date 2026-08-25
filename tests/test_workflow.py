import pytest

from app_orchestrator.workflow import (
    ApplicationWorkflow,
    PipelineMessage,
)
from app_orchestrator.providers import ProviderRegistry
from app_orchestrator.state import PipelineState
from app_orchestrator.workspace import Workspace


class FakeAgent:
    def __init__(self, result):
        self.result = result
        self.calls = 0

    def run(self):
        self.calls += 1
        return self.result


@pytest.mark.anyio
async def test_pipeline_message_is_preserved():
    message = PipelineMessage(
        requirements="Build a test application",
    )

    message.results["interaction"] = {
        "status": "clarified",
    }

    assert message.requirements == "Build a test application"
    assert message.results["interaction"]["status"] == "clarified"
    assert message.error is None


def test_application_workflow_builds(tmp_path):
    workspace = Workspace(tmp_path)
    state = PipelineState()

    provider_registry = ProviderRegistry()
    provider_registry.load_config()

    workflow = ApplicationWorkflow(
        workspace=workspace,
        state=state,
        provider_registry=provider_registry,
    )

    assert workflow.workflow is not None
    assert workflow.interaction.id == "interaction"
    assert workflow.requirement.id == "requirement-enhancement"
    assert workflow.implementation.id == "implementation"
    assert workflow.compile.id == "compile"