"""Base agent class with file I/O and execution."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
import logging
from pathlib import Path

from .workspace import Workspace
from .state import PipelineState
from .providers import ProviderRegistry, BaseProvider

logger = logging.getLogger(__name__)

class Agent(ABC):
    """Base class for all agents."""
    
    def __init__(self, workspace: Workspace, state: PipelineState, provider_registry: ProviderRegistry):
        self.workspace = workspace
        self.state = state
        self.provider_registry = provider_registry
        self.provider_chain = self._get_provider_chain()
    
    @abstractmethod
    def _get_provider_chain(self) -> List[str]:
        """Return the list of provider names for this agent (from mapping.yaml)."""
        pass
    
    @abstractmethod
    def _build_prompt(self, context: Dict[str, Any]) -> str:
        """Build the prompt for the LLM based on current context and artifacts."""
        pass
    
    @abstractmethod
    def _parse_response(self, response: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Parse the LLM response and update artifacts/state."""
        pass
    
    def run(self) -> Dict[str, Any]:
        """Execute the agent."""
        logger.info(f"Running {self.__class__.__name__}")
        
        context = self._build_context()
        prompt = self._build_prompt(context)
        
        last_error = None
        for provider_name in self.provider_chain:
            if provider_name == "FAIL":
                break
            try:
                provider = self.provider_registry.get_provider(provider_name)
                response = provider.generate(prompt, context)
                result = self._parse_response(response.content, context)
                logger.info(f"{self.__class__.__name__} completed successfully")
                return result
            except Exception as e:
                last_error = e
                logger.warning(f"Provider {provider_name} failed: {e}")
                continue
        
        error_msg = f"All providers failed for {self.__class__.__name__}. Last error: {last_error}"
        self.state.add_error(error_msg)
        raise RuntimeError(error_msg)
    
    def _build_context(self) -> Dict[str, Any]:
        # IMPORTANT: Convert state to dict to avoid JSON serialization errors
        context = {
            "workspace": self.workspace,
            "state": self.state.to_dict(),  # <-- FIXED: convert to dict
            "artifacts": {},
            "loop_a_iteration": self.state.loop_a_iteration,
            "loop_b_iteration": self.state.loop_b_iteration,
        }
        for filename in self.workspace.list_files():
            content = self.workspace.read(filename)
            if content is not None:
                context["artifacts"][filename] = content
        return context
    
    def _read_artifact(self, filename: str) -> Optional[str]:
        """Helper to read an artifact from workspace."""
        return self.workspace.read(filename)
    
    def _write_artifact(self, filename: str, content: str):
        """Helper to write an artifact to workspace."""
        self.workspace.write(filename, content)
