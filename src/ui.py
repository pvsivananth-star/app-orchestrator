#!/usr/bin/env python3
"""
App Orchestrator - Streamlit UI.

This UI is intentionally thin:
    UI -> Orchestrator -> Workflow/Agents

The UI is responsible for:
- selecting a target repository
- submitting requirements
- displaying execution status
- displaying generated artifacts
- displaying errors
- committing generated changes

It does not contain orchestration logic.
"""

from __future__ import annotations

import subprocess
import sys
import threading
import traceback
from pathlib import Path
from queue import Empty, Queue
from typing import Any

import streamlit as st


# ---------------------------------------------------------------------------
# Import application package
# ---------------------------------------------------------------------------

# ui.py lives inside <project>/src/.
# Add <project>/src/ to sys.path, not <project>/src/src/.
SRC_DIR = Path(__file__).resolve().parent

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from app_orchestrator.orchestrator import Orchestrator


# ---------------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="App Orchestrator",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

def initialise_session_state() -> None:
    defaults: dict[str, Any] = {
        "messages": [],
        "status": "idle",
        "repo_path": None,
        "repo_valid": False,
        "requirements": None,
        "error_log": None,
        "run_result": None,
        "worker": None,
        "result_queue": Queue(),
        "run_id": 0,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


initialise_session_state()


# ---------------------------------------------------------------------------
# Repository helpers
# ---------------------------------------------------------------------------

def validate_repo_path(path_str: str) -> tuple[bool, str]:
    """Validate and normalize a target Git repository path."""

    try:
        path = Path(path_str).expanduser().resolve()

        if not path.exists():
            return False, f"Path does not exist: {path}"

        if not path.is_dir():
            return False, f"Path is not a directory: {path}"

        if not (path / ".git").exists():
            return False, f"Not a Git repository: {path}"

        return True, str(path)

    except Exception as exc:
        return False, f"Invalid repository path: {exc}"


def set_repo_path(path_str: str) -> None:
    """Set the target repository."""

    path_str = path_str.strip()

    if not path_str:
        st.error("Please enter a repository path.")
        return

    valid, result = validate_repo_path(path_str)

    if not valid:
        st.session_state.repo_valid = False
        st.session_state.repo_path = None
        st.error(f"❌ {result}")
        return

    st.session_state.repo_path = result
    st.session_state.repo_valid = True
    st.session_state.status = "idle"
    st.session_state.error_log = None

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": (
                f"✅ **Repository selected**\n\n"
                f"`{result}`\n\n"
                "Enter your application requirements below."
            ),
        }
    )


def get_repo_stats(repo_path: str) -> dict[str, int]:
    """Return lightweight repository statistics."""

    repo = Path(repo_path)

    try:
        python_files = sum(
            1
            for path in repo.rglob("*.py")
            if ".git" not in path.parts
            and ".venv" not in path.parts
            and "venv" not in path.parts
            and "__pycache__" not in path.parts
        )

        return {
            "python_files": python_files,
        }

    except Exception:
        return {
            "python_files": 0,
        }


# ---------------------------------------------------------------------------
# Artifact helpers
# ---------------------------------------------------------------------------

def get_ox2_files(repo_path: str) -> dict[str, str]:
    """Read generated .ox2 artifacts."""

    if not repo_path:
        return {}

    ox2_path = Path(repo_path) / ".ox2"

    if not ox2_path.exists() or not ox2_path.is_dir():
        return {}

    files: dict[str, str] = {}

    for filepath in sorted(ox2_path.iterdir()):
        if not filepath.is_file():
            continue

        try:
            files[filepath.name] = filepath.read_text(
                encoding="utf-8",
                errors="replace",
            )
        except Exception as exc:
            files[filepath.name] = f"[Error reading file: {exc}]"

    return files


def get_changed_files(repo_path: str) -> list[str]:
    """Return Git working-tree changes."""

    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
        )

        return [
            line
            for line in result.stdout.splitlines()
            if line.strip()
        ]

    except Exception:
        return []


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------

def run_orchestrator_worker(
        repo_path: str,
        requirements: str,
        result_queue: Queue,
) -> None:
    """
    Execute the orchestrator outside the Streamlit request thread.

    The worker communicates only through result_queue.
    """

    try:
        result_queue.put(
            (
                "status",
                {
                    "status": "starting",
                    "message": "Starting orchestrator...",
                },
            )
        )

        orchestrator = Orchestrator(Path(repo_path))

        result = orchestrator.run(requirements)

        result_queue.put(
            (
                "success",
                result,
            )
        )

    except Exception:
        result_queue.put(
            (
                "error",
                traceback.format_exc(),
            )
        )


# ---------------------------------------------------------------------------
# Run management
# ---------------------------------------------------------------------------

def clear_result_queue() -> None:
    """Remove stale worker messages."""

    result_queue: Queue = st.session_state.result_queue

    while True:
        try:
            result_queue.get_nowait()
        except Empty:
            break


def start_orchestration(requirements: str) -> None:
    """Start an orchestration run."""

    if not st.session_state.repo_valid:
        st.error("Please select a valid repository first.")
        return

    if st.session_state.status == "processing":
        return

    requirements = requirements.strip()

    if not requirements:
        return

    clear_result_queue()

    st.session_state.run_id += 1
    st.session_state.requirements = requirements
    st.session_state.status = "processing"
    st.session_state.error_log = None
    st.session_state.run_result = None

    st.session_state.messages.append(
        {
            "role": "user",
            "content": requirements,
        }
    )

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": (
                "⏳ **Orchestration started.**\n\n"
                "The orchestrator is working in the background."
            ),
        }
    )

    worker = threading.Thread(
        target=run_orchestrator_worker,
        args=(
            st.session_state.repo_path,
            requirements,
            st.session_state.result_queue,
        ),
        daemon=True,
    )

    st.session_state.worker = worker
    worker.start()


def process_worker_messages() -> None:
    """
    Process all available worker messages.

    This function is intentionally safe to call on every Streamlit rerun.
    """

    result_queue: Queue = st.session_state.result_queue

    while True:
        try:
            message_type, data = result_queue.get_nowait()
        except Empty:
            break

        if message_type == "status":
            # Keep the latest status available for the UI.
            continue

        if message_type == "success":
            st.session_state.status = "done"
            st.session_state.run_result = data
            st.session_state.error_log = None

            if isinstance(data, dict):
                message = data.get(
                    "message",
                    "Orchestration completed successfully.",
                )
            else:
                message = str(data)

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": (
                        "✅ **Orchestration completed.**\n\n"
                        f"{message}"
                    ),
                }
            )

        elif message_type == "error":
            st.session_state.status = "error"
            st.session_state.error_log = str(data)

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": (
                        "❌ **Orchestration failed.**\n\n"
                        "See **Error Log** in the sidebar for details."
                    ),
                }
            )


def reset_run() -> None:
    """Reset the current orchestration state without changing the repository."""

    clear_result_queue()

    st.session_state.status = "idle"
    st.session_state.requirements = None
    st.session_state.error_log = None
    st.session_state.run_result = None
    st.session_state.worker = None
    st.session_state.messages = []


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def commit_changes(repo_path: str) -> None:
    """
    Commit generated changes.

    Only files currently reported by Git are committed.
    """

    repo = Path(repo_path)

    if not (repo / ".git").exists():
        st.error("Not a Git repository.")
        return

    try:
        status_result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        )

        if not status_result.stdout.strip():
            st.info("No changes to commit.")
            return

        subprocess.run(
            ["git", "add", "-A"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        )

        subprocess.run(
            [
                "git",
                "commit",
                "-m",
                "Orchestrator automated commit",
            ],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        )

        st.success("✅ Changes committed successfully.")

    except subprocess.CalledProcessError as exc:
        details = (
                exc.stderr
                or exc.stdout
                or "Unknown Git error."
        )
        st.error(f"Commit failed:\n\n{details}")


# ---------------------------------------------------------------------------
# Polling
# ---------------------------------------------------------------------------

process_worker_messages()

worker = st.session_state.worker

if (
        st.session_state.status == "processing"
        and worker is not None
        and not worker.is_alive()
):
    # The worker has exited but did not send a result.
    # Treat this as an unexpected failure rather than leaving the UI stuck.
    st.session_state.status = "error"

    if not st.session_state.error_log:
        st.session_state.error_log = (
            "The orchestrator worker stopped without returning a result."
        )


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("📁 Project")

    current_directory = str(Path.cwd())
    home_directory = str(Path.home())

    st.caption("Quick paths")

    col1, col2 = st.columns(2)

    with col1:
        if st.button(
                "📂 Current",
                use_container_width=True,
        ):
            st.session_state.repo_input_value = current_directory

    with col2:
        if st.button(
                "🏠 Home",
                use_container_width=True,
        ):
            st.session_state.repo_input_value = home_directory

    repo_input = st.text_input(
        "Repository path",
        value=st.session_state.get("repo_input_value", ""),
        placeholder="/path/to/git/repository",
    )

    col1, col2 = st.columns(2)

    with col1:
        if st.button(
                "Set Path",
                type="primary",
                use_container_width=True,
        ):
            set_repo_path(repo_input)
            st.rerun()

    with col2:
        if st.button(
                "Refresh",
                use_container_width=True,
        ):
            st.rerun()

    if st.session_state.repo_valid:
        st.success("Repository ready")

        st.caption(st.session_state.repo_path)

        stats = get_repo_stats(
            st.session_state.repo_path
        )

        st.metric(
            "Python files",
            stats["python_files"],
        )

    else:
        st.warning("No repository selected.")

    st.divider()

    # -----------------------------------------------------------------------
    # Run controls
    # -----------------------------------------------------------------------

    st.header("⚙️ Run")

    status = st.session_state.status

    status_display = {
        "idle": "🟢 Ready",
        "processing": "🟡 Processing",
        "done": "✅ Complete",
        "error": "🔴 Failed",
    }

    st.markdown(
        f"**Status:** {status_display.get(status, status)}"
    )

    if status == "processing":
        st.progress(0.5, text="Orchestrator running...")

    if st.button(
            "🔄 New Run",
            use_container_width=True,
            disabled=(status == "processing"),
    ):
        reset_run()
        st.rerun()

    # -----------------------------------------------------------------------
    # Git changes
    # -----------------------------------------------------------------------

    st.divider()
    st.header("📝 Git Changes")

    if st.session_state.repo_valid:
        changed_files = get_changed_files(
            st.session_state.repo_path
        )

        if changed_files:
            for changed in changed_files:
                st.code(changed, language="text")
        else:
            st.caption("Working tree clean.")

        if st.button(
                "💾 Commit Changes",
                use_container_width=True,
                disabled=(not changed_files or status == "processing"),
        ):
            commit_changes(st.session_state.repo_path)
            st.rerun()

    # -----------------------------------------------------------------------
    # Artifacts
    # -----------------------------------------------------------------------

    st.divider()
    st.header("📦 Artifacts")

    if st.session_state.repo_valid:
        artifacts = get_ox2_files(
            st.session_state.repo_path
        )

        if artifacts:
            for filename, content in artifacts.items():
                with st.expander(
                        f"📄 {filename}",
                        expanded=False,
                ):
                    st.code(
                        content,
                        language="text",
                    )
        else:
            st.caption(
                "No .ox2 artifacts found."
            )
    else:
        st.caption(
            "Select a repository first."
        )

    # -----------------------------------------------------------------------
    # Errors
    # -----------------------------------------------------------------------

    if st.session_state.error_log:
        st.divider()
        st.header("❌ Error")

        with st.expander(
                "Show error log",
                expanded=True,
        ):
            st.code(
                st.session_state.error_log,
                language="text",
            )


# ---------------------------------------------------------------------------
# Main UI
# ---------------------------------------------------------------------------

st.title("🚀 App Orchestrator")

st.caption(
    "Natural language → orchestrator → generated application"
)


# ---------------------------------------------------------------------------
# Status banner
# ---------------------------------------------------------------------------

if st.session_state.status == "processing":
    st.info(
        "⏳ The orchestrator is running. "
        "The page will update when the current run completes."
    )

elif st.session_state.status == "done":
    st.success(
        "✅ Generation completed. "
        "Review the generated artifacts and Git changes."
    )

elif st.session_state.status == "error":
    st.error(
        "❌ Generation failed. "
        "Check the error log in the sidebar."
    )


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

col_chat, col_status = st.columns(
    [2.5, 1],
)

with col_chat:
    st.subheader("💬 Requirements")

    if not st.session_state.messages:
        st.markdown(
            """
            Describe the application you want to build.

            **Example**

            > Build a simple expense tracker with a Python backend,
            > SQLite database and REST API.
            """
        )

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    can_submit = (
            st.session_state.repo_valid
            and st.session_state.status != "processing"
    )

    if not st.session_state.repo_valid:
        input_placeholder = (
            "Set a repository in the sidebar first..."
        )
    elif st.session_state.status == "processing":
        input_placeholder = (
            "Orchestrator is processing..."
        )
    else:
        input_placeholder = (
            "Describe the application you want to build..."
        )

    prompt = st.chat_input(
        input_placeholder,
        disabled=not can_submit,
    )

    if prompt:
        start_orchestration(prompt)
        st.rerun()


# ---------------------------------------------------------------------------
# Status panel
# ---------------------------------------------------------------------------

with col_status:
    st.subheader("📊 Run Status")

    status = st.session_state.status

    if status == "idle":
        st.success("Ready")

    elif status == "processing":
        st.warning("Processing")

    elif status == "done":
        st.success("Complete")

    elif status == "error":
        st.error("Failed")

    if st.session_state.repo_valid:
        st.caption("Repository")
        st.code(
            st.session_state.repo_path,
            language="text",
        )

    if st.session_state.requirements:
        st.caption("Current requirements")

        st.markdown(
            st.session_state.requirements
        )

    st.divider()

    st.markdown(
        """
        **Workflow**

        1. Requirements
        2. Orchestrator
        3. Generation
        4. Validation
        5. Generated artifacts
        6. Git review
        """
    )


# ---------------------------------------------------------------------------
# Run result
# ---------------------------------------------------------------------------

if st.session_state.run_result is not None:
    with st.expander(
            "🔎 Raw orchestration result",
            expanded=False,
    ):
        result = st.session_state.run_result

        if isinstance(result, dict):
            st.json(result)
        else:
            st.write(result)


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

st.divider()

st.caption(
    "🚀 App Orchestrator v0.1.0"
)