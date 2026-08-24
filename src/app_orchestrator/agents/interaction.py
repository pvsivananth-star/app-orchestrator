"""Interaction Agent – clarifies user requirements, suggests best practices."""

from typing import Dict, Any, List
import logging
from ..agent import Agent

logger = logging.getLogger(__name__)

class InteractionAgent(Agent):
    def _get_provider_chain(self) -> List[str]:
        return self.provider_registry.get_agent_providers("interaction")

    def _build_prompt(self, context: Dict[str, Any]) -> str:
        # Read the user's original requirements from the workspace
        user_req = self._read_artifact("user_requirements.md")
        if not user_req:
            user_req = "No requirements provided."

        # Build a system prompt for the interaction agent
        # IMPORTANT: This is an f-string so {user_req} is replaced with the actual value
        prompt = f"""You are the Interaction Agent for an AI-powered software development orchestrator.

Your role is to:
1. Clarify the user's requirements for a software project.
2. Ask targeted questions to fill any gaps (e.g., language, framework, target platform, constraints).
3. Suggest industry-standard best practices (e.g., testing, CI/CD, security).
4. Output a clear, structured set of confirmed requirements.

The user provided:
{user_req}

text

Based on this, you MUST:
- Identify unclear or missing aspects.
- Propose reasonable defaults for anything missing.
- Provide a final requirements summary in the following format:

CLARIFIED_REQUIREMENTS:
[One-sentence summary of what the user wants]

DETAILS:
- Language: [e.g., Python 3.14]
- Framework: [e.g., FastAPI, Flask, none]
- Purpose: [e.g., REST API, CLI tool, web app]
- Constraints: [e.g., memory, speed, security]
- Testing: [e.g., unit tests with pytest]
- CI/CD: [e.g., GitHub Actions]
- Other: [any other details]

QUESTIONS (if any):
[list any remaining questions for the user]

OUTPUT ONLY the above sections, with no extra commentary.
"""
        return prompt

    def _parse_response(self, response: str, context: Dict[str, Any]) -> Dict[str, Any]:
        # Write the clarified requirements to an artifact
        self._write_artifact("clarified_requirements.md", response)

        # Store in state metadata
        if not hasattr(self.state, "metadata"):
            self.state.metadata = {}
        self.state.metadata["clarified_requirements"] = response

        return {
            "clarified_requirements": response,
            "status": "clarified"
        }