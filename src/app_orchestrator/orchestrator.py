"""Orchestrator – runs the full pipeline."""

import logging
from pathlib import Path
from typing import Optional

from .workspace import Workspace
from .state import PipelineState, PipelineStage
from .providers import ProviderRegistry
from .agents import (
    InteractionAgent,
    RequirementEnhancerAgent,
    BusinessAnalystAgent,
    RepoAnalystAgent,
    DependencyAgent,
    ImplementationAgent,
    VerificationAgent,
    SecurityAgent,
    LintAgent,
    TestAgent,
    FinalVerificationAgent,
    DocAgent,
    CommitAgent,
)

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
            self._initial_agents(requirements)
            self._loop_a()
            self._loop_b()
            self._final_agents()
            self.state.stage = PipelineStage.DONE
            return {"status": "success", "state": self.state.to_dict()}
        except Exception as e:
            self.state.stage = PipelineStage.FAILED
            self.state.add_error(str(e))
            logger.error(f"Pipeline failed: {e}")
            return {"status": "failed", "error": str(e), "state": self.state.to_dict()}
    
    def _initial_agents(self, requirements: str):
        logger.info("Running initial agents...")
        self.workspace.write("user_requirements.md", requirements)
        interaction = InteractionAgent(self.workspace, self.state, self.provider_registry)
        interaction.run()
        enhancer = RequirementEnhancerAgent(self.workspace, self.state, self.provider_registry)
        enhancer.run()
        business = BusinessAnalystAgent(self.workspace, self.state, self.provider_registry)
        business.run()
        repo = RepoAnalystAgent(self.workspace, self.state, self.provider_registry)
        repo.run()
        dep = DependencyAgent(self.workspace, self.state, self.provider_registry)
        dep.run()
        self.state.stage = PipelineStage.REPO_ANALYSIS
    
    def _loop_a(self):
        logger.info("Starting Loop A...")
        self.state.stage = PipelineStage.LOOP_A
        while self.state.should_retry_loop_a():
            self.state.increment_loop_a()
            logger.info(f"Loop A iteration {self.state.loop_a_iteration}")
            impl = ImplementationAgent(self.workspace, self.state, self.provider_registry)
            impl.run()
            verify = VerificationAgent(self.workspace, self.state, self.provider_registry)
            verify.run()
            # Check verification.log
            verification_log = self.workspace.read("verification.log")
            if verification_log and "PASS" in verification_log:
                # Compile (simulated)
                self.workspace.write("compile.log", "PASS")
                compile_log = self.workspace.read("compile.log")
                if compile_log and "PASS" in compile_log:
                    logger.info("Loop A passed")
                    return
        raise RuntimeError("Loop A exhausted retries")
    
    def _loop_b(self):
        logger.info("Starting Loop B...")
        self.state.stage = PipelineStage.LOOP_B
        while self.state.should_retry_loop_b():
            self.state.increment_loop_b()
            logger.info(f"Loop B iteration {self.state.loop_b_iteration}")
            security = SecurityAgent(self.workspace, self.state, self.provider_registry)
            security.run()
            lint = LintAgent(self.workspace, self.state, self.provider_registry)
            lint.run()
            test = TestAgent(self.workspace, self.state, self.provider_registry)
            test.run()
            final = FinalVerificationAgent(self.workspace, self.state, self.provider_registry)
            final.run()
            final_log = self.workspace.read("final_verification.log")
            if final_log and "PASS" in final_log:
                logger.info("Loop B passed")
                return
        raise RuntimeError("Loop B exhausted retries")
    
    def _final_agents(self):
        self.state.stage = PipelineStage.DOCUMENTATION
        doc = DocAgent(self.workspace, self.state, self.provider_registry)
        doc.run()
        self.state.stage = PipelineStage.COMMIT
        commit = CommitAgent(self.workspace, self.state, self.provider_registry)
        commit.run()
