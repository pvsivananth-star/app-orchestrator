"""Orchestrator – runs the agent pipeline."""

import logging
import json
from pathlib import Path
from .workspace import Workspace
from .state import PipelineState, PipelineStage
from .providers import ProviderRegistry
from .agents.interaction import InteractionAgent

logger = logging.getLogger(__name__)

class Orchestrator:
    def __init__(self, repo_path: Path):
        self.repo_path = repo_path
        self.workspace = Workspace(repo_path)
        self.state = PipelineState()
        self.provider_registry = ProviderRegistry()
        self.provider_registry.load_config()
    
    def run(self, requirements: str) -> dict:
        """Run the orchestrator."""
        try:
            # Write initial requirements
            self.workspace.write("user_requirements.md", requirements)
            
            # Run interaction agent
            logger.info("Starting InteractionAgent")
            interaction = InteractionAgent(
                self.workspace,
                self.state,
                self.provider_registry
            )
            result = interaction.run()
            
            # Write state as JSON (using to_dict())
            self.workspace.write_json("state.json", self.state.to_dict())
            
            self.state.stage = PipelineStage.DONE
            return {
                "status": "success",
                "message": f"Interaction completed: {result.get('clarified_requirements', 'No clarification')[:200]}",
                "state": self.state.to_dict()
            }
        except Exception as e:
            self.state.stage = PipelineStage.FAILED
            self.state.add_error(str(e))
            logger.error(f"Pipeline failed: {e}")
            # Write error state (using to_dict())
            self.workspace.write_json("state.json", self.state.to_dict())
            return {
                "status": "failed",
                "error": str(e),
                "state": self.state.to_dict()
            }
