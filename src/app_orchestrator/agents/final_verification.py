"""FinalVerificationAgent placeholder."""
from typing import Dict, Any, List
from ..agent import Agent

class FinalVerificationAgent(Agent):
    def _get_provider_chain(self) -> List[str]:
        return self.provider_registry.get_agent_providers("final_verification")
    
    def _build_prompt(self, context: Dict[str, Any]) -> str:
        # TODO: implement prompt building
        return "FinalVerificationAgent prompt"
    
    def _parse_response(self, response: str, context: Dict[str, Any]) -> Dict[str, Any]:
        # TODO: implement parsing
        return {"status": "ok"}
