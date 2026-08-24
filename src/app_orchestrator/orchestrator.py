"""Orchestrator – runs the agent pipeline."""

import logging
from pathlib import Path
from .workspace import Workspace
from .state import PipelineState, PipelineStage
from .providers import ProviderRegistry
from .agents.interaction import InteractionAgent
from .agents.requirement_enhancer import RequirementEnhancerAgent
from .agents.implementation import ImplementationAgent
from .agents.compile import CompileAgent

logger = logging.getLogger(__name__)

class Orchestrator:
    def __init__(self, repo_path: Path):
        self.repo_path = repo_path
        self.workspace = Workspace(repo_path)
        self.state = PipelineState()
        self.provider_registry = ProviderRegistry()
        self.provider_registry.load_config()

    def run(self, requirements: str) -> dict:
        try:
            self.workspace.write("user_requirements.md", requirements)

            # 1. Interaction Agent
            logger.info("Starting InteractionAgent")
            interaction = InteractionAgent(self.workspace, self.state, self.provider_registry)
            interaction.run()

            # 2. Requirement Enhancer
            logger.info("Starting RequirementEnhancerAgent")
            enhancer = RequirementEnhancerAgent(self.workspace, self.state, self.provider_registry)
            enhancer.run()

            # 3. Implementation Agent
            logger.info("Starting ImplementationAgent")
            impl = ImplementationAgent(self.workspace, self.state, self.provider_registry)
            impl.run()

            # 4. Compile Agent (local)
            logger.info("Starting CompileAgent")
            compile_agent = CompileAgent(self.workspace, self.state, self.provider_registry)
            compile_result = compile_agent.run()

            self.workspace.write_json("state.json", self.state.to_dict())
            self.state.stage = PipelineStage.DONE

            return {
                "status": "success",
                "message": "Requirements → Implementation → Compilation completed",
                "compile_status": compile_result.get("status"),
                "state": self.state.to_dict()
            }
        except Exception as e:
            self.state.stage = PipelineStage.FAILED
            self.state.add_error(str(e))
            logger.error(f"Pipeline failed: {e}")
            self.workspace.write_json("state.json", self.state.to_dict())
            return {
                "status": "failed",
                "error": str(e),
                "state": self.state.to_dict()
            }
