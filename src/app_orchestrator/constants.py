"""Centralized constants for the orchestrator."""

# ============================================================
# File Names
# ============================================================

FILE_USER_REQUIREMENTS = "user_requirements.md"
FILE_CLARIFIED_REQUIREMENTS = "clarified_requirements.md"
FILE_REQUIREMENTS = "requirements.md"
FILE_REPO_ANALYSIS = "repo_analysis.md"
FILE_DEPENDENCIES = "dependencies.log"
FILE_COMPILE_LOG = "compile.log"
FILE_VERIFICATION_LOG = "verification.log"
FILE_SECURITY_LOG = "security.log"
FILE_LINT_LOG = "lint.log"
FILE_TEST_LOG = "test.log"
FILE_DOCS = "docs.md"
FILE_COMMIT_LOG = "commit.log"
FILE_STATE = "state.json"
FILE_IMPLEMENTATION_PLAN = "implementation_plan.json"
FILE_IMPLEMENTATION_LOG = "implementation_log.md"
FILE_INCREMENTAL_RESULT = "incremental_generation_result.json"
FILE_USER_REQUIREMENTS = "user_requirements.md"

# ============================================================
# Defaults
# ============================================================

DEFAULT_TEMPERATURE = 0.2
DEFAULT_MAX_TOKENS = 4096
DEFAULT_TIMEOUT = 30
DEFAULT_MAX_RETRIES = 5
DEFAULT_RETRY_DELAY = 1.0
DEFAULT_MAX_CHUNK_ITERATIONS = 3
DEFAULT_MIN_REQUIREMENTS_LENGTH = 128
DEFAULT_TARGET_CHUNK_KB = 1.0
DEFAULT_MAX_CONTEXT_KB = 6.0
DEFAULT_MAX_ITERATIONS = 30

# ============================================================
# Pipeline Stages
# ============================================================

STAGE_INIT = "init"
STAGE_REQUIREMENT_CLARIFICATION = "requirement_clarification"
STAGE_REQUIREMENT_ENHANCEMENT = "requirement_enhancement"
STAGE_BUSINESS_VALIDATION = "business_validation"
STAGE_REPO_ANALYSIS = "repo_analysis"
STAGE_DEPENDENCY_SETUP = "dependency_setup"
STAGE_IMPLEMENTATION = "implementation"
STAGE_VERIFICATION = "verification"
STAGE_COMPILE = "compile"
STAGE_SECURITY = "security"
STAGE_LINT = "lint"
STAGE_TEST = "test"
STAGE_FINAL_VERIFICATION = "final_verification"
STAGE_DOCUMENTATION = "documentation"
STAGE_COMMIT = "commit"
STAGE_DONE = "done"
STAGE_FAILED = "failed"
STAGE_LOOP_A = "loop_a"
STAGE_LOOP_B = "loop_b"

# ============================================================
# Provider Error Types
# ============================================================

ERROR_RATE_LIMIT = "rate_limit"
ERROR_CONNECTION = "connection"
ERROR_TIMEOUT = "timeout"
ERROR_AUTHENTICATION = "authentication"
ERROR_INVALID_REQUEST = "invalid_request"
ERROR_SERVER_ERROR = "server_error"
ERROR_UNKNOWN = "unknown"

# ============================================================
# File Patterns
# ============================================================

IGNORED_PATH_PATTERNS = {
    ".git",
    ".ox2",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
    "target",
    ".idea",
}

PREFERRED_FILES = [
    "README.md",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "package.json",
    "pyproject.toml",
    "requirements.txt",
]

# ============================================================
# Response Patterns
# ============================================================

FILE_PATTERN = r"##\s*FILE:\s*([^\n]+?)\s*\n```(?:python|text)?\s*\n(.*?)```"
FILE_PATTERN_NO_LANG = r"##\s*FILE:\s*([^\n]+?)\s*\n```\n(.*?)```"
FILE_PATTERN_NO_BLOCK = r"##\s*FILE:\s*([^\n]+?)\s*\n(.*?)(?=\n##\s*FILE:|$)"
CODE_BLOCK_PATTERN = r"```(?:python|text)\s*\n(.*?)```"

# ============================================================
# Agent Names
# ============================================================

AGENT_INTERACTION = "interaction"
AGENT_REQUIREMENT_ENHANCER = "requirement_enhancer"
AGENT_BUSINESS_ANALYST = "business_analyst"
AGENT_REPO_ANALYST = "repo_analyst"
AGENT_DEPENDENCY = "dependency"
AGENT_IMPLEMENTATION = "implementation"
AGENT_VERIFICATION = "verification"
AGENT_SECURITY = "security"
AGENT_LINT = "lint"
AGENT_TEST = "test"
AGENT_FINAL_VERIFICATION = "final_verification"
AGENT_DOC = "doc"
AGENT_COMMIT = "commit"
