#!/bin/bash
# add_requirement_enhancer.sh

echo "=== Adding Requirement Enhancer Agent ==="

# 1. Create requirement_enhancer.py
cat > src/app_orchestrator/agents/requirement_enhancer.py << 'EOF'
"""Requirement Enhancer Agent – expands clarified requirements into detailed specs."""

from typing import Dict, Any, List
import logging
from ..agent import Agent

logger = logging.getLogger(__name__)

class RequirementEnhancerAgent(Agent):
    def _get_provider_chain(self) -> List[str]:
        return self.provider_registry.get_agent_providers("requirement_enhancer")

    def _build_prompt(self, context: Dict[str, Any]) -> str:
        clarified = self._read_artifact("clarified_requirements.md")
        if not clarified:
            clarified = "No clarified requirements found."

        user_req = self._read_artifact("user_requirements.md")
        if not user_req:
            user_req = "No user requirements found."

        prompt = f"""You are the Requirement Enhancer Agent for an AI-powered software development orchestrator.

Your role is to expand clarified requirements into detailed, actionable specifications.

The Interaction Agent provided this clarified summary:
{clarified}

text

The user's original request was:
{user_req}

text

Based on this, you MUST produce a comprehensive requirements document with:

1. **Overview** – 2-3 sentences describing the project
2. **User Stories** – List of user stories
3. **Functional Requirements** – Detailed list of what the system must do
4. **Non-Functional Requirements** – Performance, security, usability
5. **Technical Specifications** – Architecture, stack, patterns
6. **Acceptance Criteria** – How to verify each requirement
7. **Out of Scope** – What is explicitly NOT included

OUTPUT in the following format:

# Requirements Specification

## Overview
[Description]

## User Stories
- As a [role], I want to [action], so that [benefit]

## Functional Requirements
- FR-1: [description]
- FR-2: [description]

## Non-Functional Requirements
- NFR-1: [description]

## Technical Specifications
- Language: [e.g., Python 3.14]
- Framework: [e.g., FastAPI]
- Architecture: [e.g., REST API, CLI]

## Acceptance Criteria
- AC-1: [condition]

## Out of Scope
- [feature]

Keep the output concise but comprehensive. Be specific and actionable.
"""
        return prompt

    def _parse_response(self, response: str, context: Dict[str, Any]) -> Dict[str, Any]:
        self._write_artifact("requirements.md", response)

        if not hasattr(self.state, "metadata"):
            self.state.metadata = {}
        self.state.metadata["requirements_enhanced"] = response[:200] + "..." if len(response) > 200 else response

        return {
            "requirements_enhanced": response,
            "status": "enhanced"
        }
EOF

# 2. Update __init__.py
cat > src/app_orchestrator/agents/__init__.py << 'EOF'
"""Agent implementations."""
from .interaction import InteractionAgent
from .requirement_enhancer import RequirementEnhancerAgent

__all__ = [
    "InteractionAgent",
    "RequirementEnhancerAgent",
]
EOF

# 3. Update orchestrator.py
cat > src/app_orchestrator/orchestrator.py << 'EOF'
"""Orchestrator – runs the agent pipeline."""

import logging
from pathlib import Path
from .workspace import Workspace
from .state import PipelineState, PipelineStage
from .providers import ProviderRegistry
from .agents.interaction import InteractionAgent
from .agents.requirement_enhancer import RequirementEnhancerAgent

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

            logger.info("Starting InteractionAgent")
            interaction = InteractionAgent(self.workspace, self.state, self.provider_registry)
            interaction.run()

            logger.info("Starting RequirementEnhancerAgent")
            enhancer = RequirementEnhancerAgent(self.workspace, self.state, self.provider_registry)
            enhancer.run()

            self.workspace.write_json("state.json", self.state.to_dict())
            self.state.stage = PipelineStage.DONE

            return {
                "status": "success",
                "message": "Requirements clarification and enhancement completed",
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
EOF

# 4. Clean cache
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true

echo "✅ Requirement Enhancer Agent added"
echo ""
echo "Test with: ./test_hello.sh"
EOF